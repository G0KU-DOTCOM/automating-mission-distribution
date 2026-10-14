"""Merge synthetic source updates and preserve channel task identity and ownership."""

import json

from .models import Channel, DemoDataError, DirectRules, IndirectRules, parse_opportunity
from .routing import Decision, route_direct, route_indirect
from .source_data import SourceBatch, SourceRecord, json_text
from .storage import DemoStore


SCALARS = ("title", "buyer_name", "buyer_org_number", "main_trade", "area", "deadline",
           "description", "notice_status")
CONFLICT_FIELDS = frozenset({"buyer_org_number", "main_trade", "area", "deadline", "notice_status"})
MISSING_FIELDS = ("buyer_org_number", "main_trade", "area", "deadline")


def _normal(value: str) -> str:
    return " ".join(value.casefold().split())


def _fallback_key(payload: dict) -> tuple | None:
    if not payload.get("buyer_org_number") or not payload.get("deadline"):
        return None
    return (payload["buyer_org_number"], _normal(payload["title"]), payload["deadline"])


def _identity(store: DemoStore, record: SourceRecord) -> tuple[str | None, list[str]]:
    connection = store.connection
    existing = connection.execute("SELECT competition_id FROM source_records WHERE source = ? AND record_id = ?",
                                  (record.source, record.record_id)).fetchone()
    reference = connection.execute("SELECT id FROM competitions WHERE competition_ref = ?",
                                   (record.competition_ref,)).fetchone() if record.competition_ref else None
    if existing:
        current = connection.execute("SELECT competition_ref FROM competitions WHERE id = ?",
                                     (existing["competition_id"],)).fetchone()["competition_ref"]
        if record.competition_ref and current and current != record.competition_ref:
            raise DemoDataError("En kjent kilde-ID peker på en annen konkurransereferanse. Identiteten må avklares.")
        if reference and reference["id"] != existing["competition_id"]:
            raise DemoDataError("Kilde-ID og konkurransereferanse peker på forskjellige lagrede konkurranser. Manuell avklaring kreves.")
        return existing["competition_id"], []
    if reference:
        return reference["id"], []
    key = _fallback_key(record.payload)
    exact, possible = [], []
    for row in connection.execute("SELECT id, competition_ref, payload_json FROM competitions").fetchall():
        # Different known competition references must never be collapsed by a similar title.
        if record.competition_ref and row["competition_ref"] and record.competition_ref != row["competition_ref"]:
            continue
        public = json.loads(row["payload_json"])["opportunity"]
        if key is not None and _fallback_key(public) == key:
            exact.append(row["id"])
        same_buyer = (
            record.payload.get("buyer_org_number") == public.get("buyer_org_number")
            if record.payload.get("buyer_org_number") and public.get("buyer_org_number")
            else _normal(record.payload["buyer_name"]) == _normal(public["buyer_name"])
        )
        if same_buyer and _normal(record.payload["title"]) == _normal(public["title"]):
            possible.append(row["id"])
    if len(exact) == 1:
        return exact[0], []
    return None, sorted(set(possible + exact))


def _canonical(store: DemoStore, competition_id: str) -> dict:
    previous = store.competition(competition_id)
    old = previous.get("opportunity", {})
    snapshots = store.connection.execute("""
        SELECT source, record_id, modified_at, payload_json FROM source_records
        WHERE competition_id = ? ORDER BY modified_at DESC, source, record_id
    """, (competition_id,)).fetchall()
    payloads = [(row, json.loads(row["payload_json"])) for row in snapshots]
    public, origins, conflicts = {"id": competition_id}, {}, {}
    for field in SCALARS:
        values = [(row, value[field]) for row, value in payloads if value.get(field) is not None]
        if values:
            public[field] = values[0][1]
            origins[field] = {"source": values[0][0]["source"], "record_id": values[0][0]["record_id"],
                              "modified_at": values[0][0]["modified_at"]}
            if field in CONFLICT_FIELDS and len({json_text(value) for _, value in values}) > 1:
                conflicts[field] = [{"source": row["source"], "record_id": row["record_id"], "value": value}
                                    for row, value in values]
        else:
            # Missing source values do not erase previously known information.
            public[field] = old.get(field)
            if field in previous.get("field_origins", {}):
                origins[field] = previous["field_origins"][field]
    public["notice_status"] = public["notice_status"] or "active"
    for field in ("other_trades", "public_flags", "document_urls"):
        values = []
        for _, payload in payloads:
            for value in payload.get(field, []):
                if value not in values:
                    values.append(value)
        # Document removal and explicit clearing are outside this demo contract.
        if field == "document_urls":
            for value in old.get(field, []):
                if value not in values:
                    values.append(value)
        public[field] = values
    public["other_trades"] = [trade for trade in public["other_trades"] if trade != public["main_trade"]]
    possible = previous.get("possible_duplicate_ids", [])
    if possible and "MULIG_DUPLIKAT" not in public["public_flags"]:
        public["public_flags"].append("MULIG_DUPLIKAT")
    return {
        "opportunity": public,
        "source_refs": [{"source": row["source"], "record_id": row["record_id"],
                         "modified_at": row["modified_at"]} for row in snapshots],
        "field_origins": origins,
        "missing_fields": [field for field in MISSING_FIELDS if public.get(field) is None],
        "conflicts": conflicts,
        "possible_duplicate_ids": possible,
    }


def _proposal(public: dict, channel: Channel, direct: DirectRules, indirect: IndirectRules) -> dict:
    opportunity = parse_opportunity(public["opportunity"])
    if public["conflicts"]:
        return Decision(opportunity.id, opportunity.title, channel, None, "DATA_KONFLIKT",
                        "Kildene er uenige om sentrale opplysninger. Dataene må avklares før en mottaker foreslås.",
                        opportunity.main_trade, opportunity.area, opportunity.public_flags).to_dict()
    if channel == Channel.DIRECT:
        return route_direct(opportunity, direct).to_dict()
    return route_indirect(opportunity, indirect).to_dict()


def _update_tasks(store: DemoStore, competition_id: str, before: dict, after: dict,
                  direct: DirectRules, indirect: IndirectRules) -> tuple[int, int]:
    created, updated = 0, 0
    old_public, new_public = before.get("opportunity", {}), after["opportunity"]
    changed = [field for field in new_public if field != "id" and old_public.get(field) != new_public[field]]
    review_changed = any(before.get(field) != after.get(field)
                         for field in ("conflicts", "missing_fields", "possible_duplicate_ids"))
    for channel in Channel:
        row = store.connection.execute("SELECT id, payload_json FROM tasks WHERE competition_id = ? AND channel = ?",
                                       (competition_id, channel.value)).fetchone()
        if row is None:
            if new_public["notice_status"] == "cancelled":
                continue
            task = _proposal(after, channel, direct, indirect)
            task.update(task_id=store.new_id("T-"), competition_id=competition_id,
                        deadline=new_public["deadline"], lifecycle="aktiv", assignment_type="regel",
                        data_review_required=bool(after["conflicts"] or after["possible_duplicate_ids"]))
            store.connection.execute("INSERT INTO tasks (id, competition_id, channel, payload_json) VALUES (?, ?, ?, ?)",
                                     (task["task_id"], competition_id, channel.value, json_text(task)))
            store.add_event(task["task_id"], "forslag_opprettet", {"reason_code": task["reason_code"]})
            created += 1
            continue
        if not changed and not review_changed:
            continue
        task = json.loads(row["payload_json"])
        # An assigned task keeps its current owner, including a manual reassignment.
        if task["owner"] is None and task["assignment_type"] == "regel" and new_public["notice_status"] != "cancelled":
            proposal = _proposal(after, channel, direct, indirect)
            for field in ("owner", "status", "reason_code", "explanation", "flags"):
                task[field] = proposal[field]
            if task["owner"]:
                store.add_event(task["task_id"], "mottaker_foreslått", {"owner_id": task["owner"]["id"]})
        private_flags = [flag for flag in task["flags"] if flag not in new_public["public_flags"]
                         and flag in {"INSTALLERT_BASE", "EIER_INAKTIV"}]
        task.update(title=new_public["title"], main_trade=new_public["main_trade"], area=new_public["area"],
                    deadline=new_public["deadline"], flags=list(new_public["public_flags"]) + private_flags,
                    data_review_required=bool(after["conflicts"] or after["possible_duplicate_ids"]))
        if "deadline" in changed:
            store.add_event(task["task_id"], "frist_endret", {"previous": old_public.get("deadline"),
                                                             "current": new_public["deadline"]})
        if new_public["notice_status"] == "cancelled" and task["lifecycle"] != "avlyst":
            task["lifecycle"] = "avlyst"
            store.add_event(task["task_id"], "avlyst", {})
        details = [field for field in changed if field not in {"deadline", "notice_status"}]
        if details:
            store.add_event(task["task_id"], "opplysninger_endret", {"fields": details})
        if review_changed:
            store.add_event(task["task_id"], "datakontroll_endret", {
                "missing_fields": after["missing_fields"], "conflicting_fields": sorted(after["conflicts"]),
                "possible_duplicate": bool(after["possible_duplicate_ids"]),
            })
        store.connection.execute("UPDATE tasks SET payload_json = ? WHERE id = ? AND channel = ?",
                                 (json_text(task), row["id"], channel.value))
        updated += 1
    return created, updated


def ingest_batch(store: DemoStore, batch: SourceBatch, direct: DirectRules, indirect: IndirectRules) -> dict:
    report = {"batch_id": batch.id, "records_seen": len(batch.records), "created_competitions": 0,
              "created_tasks": 0, "updated_tasks": 0, "duplicate_records": 0,
              "stale_records": 0, "possible_duplicates": 0, "already_processed": False}
    connection = store.connection
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        prior_batch = connection.execute("SELECT fingerprint FROM batches WHERE id = ?", (batch.id,)).fetchone()
        if prior_batch:
            if prior_batch["fingerprint"] != batch.fingerprint:
                raise DemoDataError("En allerede innlest batch-ID har annet innhold. Bruk en ny ID for en ny batch.")
            report.update(already_processed=True, duplicate_records=len(batch.records))
            return report
        before = {}
        for record in batch.records:
            prior = connection.execute("SELECT * FROM source_records WHERE source = ? AND record_id = ?",
                                       (record.source, record.record_id)).fetchone()
            if prior:
                if record.modified_at < prior["modified_at"]:
                    report["stale_records"] += 1
                    continue
                if record.modified_at == prior["modified_at"]:
                    if record.fingerprint != prior["fingerprint"]:
                        raise DemoDataError("Samme kilde-ID og endringstid har motstridende innhold. Kildeversjonen må avklares.")
                    report["duplicate_records"] += 1
                    continue
            competition_id, possible = _identity(store, record)
            if competition_id is None:
                competition_id = store.new_id("C-")
                initial = {"opportunity": {}, "possible_duplicate_ids": possible}
                connection.execute("INSERT INTO competitions (id, competition_ref, payload_json) VALUES (?, ?, ?)",
                                   (competition_id, record.competition_ref, json_text(initial)))
                report["created_competitions"] += 1
                if possible:
                    report["possible_duplicates"] += 1
            elif record.competition_ref:
                connection.execute("UPDATE competitions SET competition_ref = COALESCE(competition_ref, ?) WHERE id = ?",
                                   (record.competition_ref, competition_id))
            if competition_id not in before:
                before[competition_id] = store.competition(competition_id)
            connection.execute("""
                INSERT INTO source_records (source, record_id, competition_id, modified_at, fingerprint, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (source, record_id) DO UPDATE SET
                    modified_at=excluded.modified_at, fingerprint=excluded.fingerprint, payload_json=excluded.payload_json
            """, (record.source, record.record_id, competition_id, record.modified_at, record.fingerprint, json_text(record.payload)))
            connection.execute("""
                INSERT INTO source_versions (source, record_id, competition_id, modified_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
            """, (record.source, record.record_id, competition_id, record.modified_at, json_text(record.payload)))
            public = _canonical(store, competition_id)
            connection.execute("UPDATE competitions SET payload_json = ? WHERE id = ?",
                               (json_text(public), competition_id))
        # Decide only after all sources in the batch are combined, avoiding premature ownership.
        for competition_id, previous in before.items():
            created, updated = _update_tasks(store, competition_id, previous, store.competition(competition_id), direct, indirect)
            report["created_tasks"] += created
            report["updated_tasks"] += updated
        for source, through in batch.read_until.items():
            connection.execute("""
                INSERT INTO sync_state (source, read_until) VALUES (?, ?)
                ON CONFLICT (source) DO UPDATE SET read_until=MAX(sync_state.read_until, excluded.read_until)
            """, (source, through))
        connection.execute("INSERT INTO batches (id, fingerprint) VALUES (?, ?)", (batch.id, batch.fingerprint))
    return report
