"""Local administrator-only demo storage; no application authentication yet."""

import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .approval import (StaleProposalError, advance_review_version, approval_blocker, approval_current, invalidate_approval,
                       now_utc, review_revision)
from .models import Channel, DemoDataError, Person
from .source_data import json_text


class DemoStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS competitions (
                id TEXT PRIMARY KEY,
                competition_ref TEXT UNIQUE,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_records (
                source TEXT NOT NULL,
                record_id TEXT NOT NULL,
                competition_id TEXT NOT NULL REFERENCES competitions(id),
                modified_at TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (source, record_id)
            );
            CREATE TABLE IF NOT EXISTS source_versions (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                record_id TEXT NOT NULL,
                competition_id TEXT NOT NULL REFERENCES competitions(id),
                modified_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                competition_id TEXT NOT NULL REFERENCES competitions(id),
                channel TEXT NOT NULL CHECK (channel IN ('direkte', 'indirekte')),
                payload_json TEXT NOT NULL,
                UNIQUE (competition_id, channel)
            );
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(id),
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_state (
                source TEXT PRIMARY KEY,
                read_until TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL
            );
        """)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.connection.close()

    def competition(self, competition_id: str) -> dict:
        row = self.connection.execute("SELECT payload_json FROM competitions WHERE id = ?",
                                      (competition_id,)).fetchone()
        if row is None:
            raise DemoDataError("Konkurransen finnes ikke i den lokale demoen.")
        return json.loads(row["payload_json"])

    def task_for_reference(self, reference: str, channel: Channel) -> str:
        row = self.connection.execute("""
            SELECT t.id FROM tasks t JOIN competitions c ON c.id = t.competition_id
            WHERE c.competition_ref = ? AND t.channel = ?
        """, (reference, channel.value)).fetchone()
        if row is None:
            raise DemoDataError("Ingen oppgave finnes for referansen i den valgte kanalen.")
        return row["id"]

    def tasks(self, channel: Channel) -> list[dict]:
        rows = self.connection.execute("""
            SELECT t.id, t.payload_json, c.competition_ref, c.payload_json AS competition_json
            FROM tasks t JOIN competitions c ON c.id = t.competition_id
            WHERE t.channel = ? ORDER BY c.competition_ref, t.id
        """, (channel.value,)).fetchall()
        result = []
        for row in rows:
            task = json.loads(row["payload_json"])
            task["competition_ref"] = row["competition_ref"]
            task["public_opportunity"] = json.loads(row["competition_json"])
            task["events"] = [
                {"type": item["event_type"], "details": json.loads(item["payload_json"])}
                for item in self.connection.execute("""
                    SELECT event_type, payload_json FROM task_events WHERE task_id = ? ORDER BY id
                """, (row["id"],)).fetchall()
            ]
            result.append(task)
        return result

    def add_event(self, task_id: str, event_type: str, details: dict) -> None:
        self.connection.execute("INSERT INTO task_events (task_id, event_type, payload_json) VALUES (?, ?, ?)",
                                (task_id, event_type, json_text(details)))

    def assessments(self) -> list[dict]:
        """Public classification only; never include allocations or channel activity."""
        result = []
        for row in self.connection.execute("SELECT competition_ref, payload_json FROM competitions ORDER BY competition_ref, id"):
            public = json.loads(row["payload_json"])
            if "classification" in public:
                result.append({"competition_ref": row["competition_ref"],
                               "title": public["opportunity"]["title"],
                               "conflicting_fields": sorted(public["conflicts"]),
                               "classification": public["classification"]})
        return result

    def _proposal_for_action(self, task_id: str, channel: Channel, expected_revision: str | None,
                             allow_approved_replay: bool = False) -> tuple[dict, dict]:
        row = self.connection.execute("""
            SELECT t.payload_json, c.payload_json AS public_json FROM tasks t
            JOIN competitions c ON c.id = t.competition_id WHERE t.id = ? AND t.channel = ?
        """, (task_id, channel.value)).fetchone()
        if row is None:
            raise DemoDataError("Oppgaven finnes ikke i den valgte kanalen.")
        task, public = json.loads(row["payload_json"]), json.loads(row["public_json"])
        if expected_revision is not None and expected_revision != review_revision(task, public):
            replay = (allow_approved_replay and approval_current(task, public)
                      and task["approval"].get("request_revision") == expected_revision)
            if not replay:
                raise StaleProposalError("Oppgaven er endret siden du åpnet siden. Oppdater oversikten og se gjennom forslaget på nytt.")
        return task, public

    def reassign(self, task_id: str, channel: Channel, person: Person, expected_revision: str | None = None) -> dict:
        if person.channel != channel or not person.active:
            raise DemoDataError("Manuell mottaker må være aktiv og tilhøre den valgte kanalen.")
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            task, public = self._proposal_for_action(task_id, channel, expected_revision)
            if task["lifecycle"] != "aktiv":
                raise DemoDataError("Mottakeren kan ikke endres på en avlyst oppgave.")
            old_owner = task["owner"]
            if old_owner and old_owner["id"] == person.id:
                return task
            task["owner"] = {"id": person.id, "name": person.name,
                             "trade_codes": list(person.trade_codes), "active": person.active,
                             "capacity": person.capacity.value}
            task["status"] = "foreslått"
            task["reason_code"] = "MANUELL_TILDELING"
            task["explanation"] = "Mottakeren er valgt manuelt i denne kanalen. Senere oppdateringer følger denne mottakeren."
            task["assignment_type"] = "manuell"
            advance_review_version(task)
            if invalidate_approval(task, public, "Mottakeren er endret manuelt."):
                self.add_event(task_id, "godkjenning_utdatert", {"reason": "Mottakeren er endret manuelt."})
            self.connection.execute("UPDATE tasks SET payload_json = ? WHERE id = ? AND channel = ?",
                                    (json_text(task), task_id, channel.value))
            self.add_event(task_id, "manuelt_omfordelt", {
                "previous_owner_id": old_owner["id"] if old_owner else None,
                "new_owner_id": person.id,
            })
        return task

    def approve(self, task_id: str, channel: Channel, people: dict[str, Person], expected_revision: str,
                acknowledge_review: bool = False) -> dict:
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            task, public = self._proposal_for_action(task_id, channel, expected_revision, allow_approved_replay=True)
            blocker = approval_blocker(task, public)
            if blocker:
                raise DemoDataError(blocker)
            person = people.get(task["owner"]["id"])
            if person is None or person.channel != channel or not person.active:
                raise DemoDataError("Mottakeren må fortsatt være aktiv i denne kanalens ansvarsliste.")
            if task.get("data_review_required") and acknowledge_review is not True:
                raise DemoDataError("Bekreft at du har kontrollert de endrede opplysningene før godkjenning.")
            if approval_current(task, public):
                return task
            if task.get("data_review_required"):
                task.update(data_review_required=False, classification_review_required=False)
                self.add_event(task_id, "datakontroll_bekreftet", {"actor": "lokal_demobruker", "at": now_utc()})
            approved_at = now_utc()
            advance_review_version(task)
            task["approval"] = {"state": "godkjent", "review_revision": review_revision(task, public),
                                "request_revision": expected_revision,
                                "owner_id": person.id, "approved_at": approved_at,
                                "actor": "lokal_demobruker"}
            self.connection.execute("UPDATE tasks SET payload_json = ? WHERE id = ? AND channel = ?",
                                    (json_text(task), task_id, channel.value))
            self.add_event(task_id, "godkjent_lokalt", {"owner_id": person.id, "at": approved_at,
                                                      "actor": "lokal_demobruker"})
        return task

    @staticmethod
    def new_id(prefix: str) -> str:
        return prefix + uuid4().hex
