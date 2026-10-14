"""Test stable identity, transactional sync, merging and channel-local updates."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mission_distribution.ingestion import ingest_batch
from mission_distribution.models import Channel, DemoDataError, load_direct_rules, load_indirect_rules
from mission_distribution.source_data import load_source_batch, parse_source_batch
from mission_distribution.storage import DemoStore


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demo_data"
BATCHES = DATA / "source_batches"


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "demo.sqlite3"
        self.store = DemoStore(self.path)
        self.addCleanup(self.store.connection.close)
        self.direct = load_direct_rules(DATA / "direct_rules.json")
        self.indirect = load_indirect_rules(DATA / "indirect_rules.json")
        self.initial = load_source_batch(BATCHES / "01-initial.json")

    def ingest(self, batch):
        return ingest_batch(self.store, batch, self.direct, self.indirect)

    def batch(self, filename):
        return load_source_batch(BATCHES / filename)

    def raw(self, filename="01-initial.json"):
        return json.loads((BATCHES / filename).read_text(encoding="utf-8"))

    def selected(self, channel=Channel.DIRECT, reference="DEMO-COMP-101"):
        return next(task for task in self.store.tasks(channel) if task["competition_ref"] == reference)

    def count(self, table):
        # Only fixed test table names are passed here.
        return self.store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_three_source_posts_become_two_competitions_and_four_tasks(self):
        report = self.ingest(self.initial)
        self.assertEqual(report["created_competitions"], 2)
        self.assertEqual(report["created_tasks"], 4)
        self.assertEqual(self.count("source_records"), 3)
        self.assertEqual(self.count("competitions"), 2)
        self.assertEqual(self.count("tasks"), 4)

    def test_missing_fields_are_filled_before_first_assignment(self):
        self.ingest(self.initial)
        task = self.selected()
        public = task["public_opportunity"]
        self.assertEqual(public["opportunity"]["buyer_org_number"], "000000101")
        self.assertEqual(public["opportunity"]["area"], "Vest")
        self.assertEqual(public["missing_fields"], [])
        self.assertEqual(len(public["source_refs"]), 2)
        self.assertEqual(task["owner"]["id"], "D-01")
        self.assertEqual(public["field_origins"]["buyer_org_number"]["source"], "mercell")

    def test_same_batch_is_a_no_op_without_more_tasks_or_events(self):
        self.ingest(self.initial)
        before = self.store.tasks(Channel.DIRECT)
        report = self.ingest(self.initial)
        self.assertTrue(report["already_processed"])
        self.assertEqual(self.count("tasks"), 4)
        self.assertEqual(self.count("source_versions"), 3)
        self.assertEqual(self.store.tasks(Channel.DIRECT), before)

    def test_same_posts_in_a_new_batch_do_not_add_tasks(self):
        self.ingest(self.initial)
        data = self.raw()
        data["batch_id"] = "REPEATED-POSTS"
        report = self.ingest(parse_source_batch(data))
        self.assertEqual(report["duplicate_records"], 3)
        self.assertEqual(report["created_tasks"], 0)
        self.assertEqual(report["updated_tasks"], 0)
        self.assertEqual(self.count("source_versions"), 3)

    def test_deadline_and_documents_update_same_tasks(self):
        self.ingest(self.initial)
        original_ids = {channel: self.selected(channel)["task_id"] for channel in Channel}
        report = self.ingest(self.batch("02-update.json"))
        self.assertEqual(report["created_tasks"], 0)
        self.assertEqual(report["updated_tasks"], 2)
        self.assertEqual(self.count("tasks"), 4)
        for channel in Channel:
            task = self.selected(channel)
            self.assertEqual(task["task_id"], original_ids[channel])
            self.assertEqual(task["deadline"], "2026-11-27")
            self.assertEqual(len(task["public_opportunity"]["opportunity"]["document_urls"]), 2)
            events = [event for event in task["events"] if event["type"] == "frist_endret"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["details"], {"previous": "2026-11-20", "current": "2026-11-27"})

    def test_manual_owner_is_preserved_and_partner_owner_is_unchanged(self):
        self.ingest(self.initial)
        task = self.selected()
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"])
        self.ingest(self.batch("02-update.json"))
        updated = self.selected()
        self.assertEqual(updated["owner"]["id"], "D-03")
        self.assertEqual(updated["task_id"], task["task_id"])
        self.assertEqual(updated["assignment_type"], "manuell")
        self.assertEqual(updated["reason_code"], "MANUELL_TILDELING")
        self.assertEqual(self.selected(Channel.INDIRECT)["owner"]["id"], "P-01")

    def test_state_survives_reopening_database(self):
        self.ingest(self.initial)
        original = self.selected()
        with DemoStore(self.path) as other:
            self.assertEqual(other.tasks(Channel.DIRECT)[0]["task_id"], original["task_id"])

    def test_cancellation_marks_existing_task_and_keeps_owner(self):
        self.ingest(self.initial)
        original = self.selected(reference="DEMO-COMP-102")
        self.ingest(self.batch("03-cancelled.json"))
        task = self.selected(reference="DEMO-COMP-102")
        self.assertEqual(task["task_id"], original["task_id"])
        self.assertEqual(task["owner"], original["owner"])
        self.assertEqual(task["lifecycle"], "avlyst")
        self.assertTrue(any(event["type"] == "avlyst" for event in task["events"]))

    def test_older_source_version_cannot_revert_deadline_or_watermark(self):
        self.ingest(self.initial)
        self.ingest(self.batch("02-update.json"))
        data = self.raw()
        data["batch_id"] = "LATE-OLD-VERSION"
        report = self.ingest(parse_source_batch(data))
        self.assertEqual(report["stale_records"], 2)
        self.assertEqual(self.selected()["deadline"], "2026-11-27")
        through = self.store.connection.execute("SELECT read_until FROM sync_state WHERE source='doffin'").fetchone()[0]
        self.assertTrue(through.startswith("2026-10-14T09:00:00"))

    def test_fallback_key_can_join_sources_without_common_reference(self):
        data = self.raw()
        data["records"] = [copy.deepcopy(data["records"][1])]
        data["records"][0]["competition_ref"] = None
        second = copy.deepcopy(data["records"][0])
        second.update(source="doffin", record_id="NO-REF-D-101")
        data["records"].append(second)
        report = self.ingest(parse_source_batch(data))
        self.assertEqual(report["created_competitions"], 1)
        self.assertEqual(self.count("source_records"), 2)
        self.assertEqual(self.count("tasks"), 2)

    def test_changed_deadline_with_stable_source_id_does_not_need_common_reference(self):
        data = self.raw()
        data["records"] = [copy.deepcopy(data["records"][1])]
        data["records"][0]["competition_ref"] = None
        self.ingest(parse_source_batch(data))
        original = self.store.tasks(Channel.DIRECT)[0]
        data["batch_id"] = "NO-REF-UPDATE"
        data["read_until"]["mercell"] = "2026-10-14T09:00:00Z"
        data["records"][0]["modified_at"] = "2026-10-14T08:30:00Z"
        data["records"][0]["opportunity"]["deadline"] = "2026-11-27"
        self.ingest(parse_source_batch(data))
        current = self.store.tasks(Channel.DIRECT)[0]
        self.assertEqual(current["task_id"], original["task_id"])
        self.assertEqual(current["deadline"], "2026-11-27")

    def test_uncertain_duplicate_stays_separate_and_flagged(self):
        self.ingest(self.initial)
        report = self.ingest(self.batch("04-possible-duplicate.json"))
        self.assertEqual(report["possible_duplicates"], 1)
        self.assertEqual(self.count("competitions"), 3)
        flagged = [task for task in self.store.tasks(Channel.DIRECT)
                   if "MULIG_DUPLIKAT" in task["flags"]]
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0]["data_review_required"])
        self.assertEqual(len(flagged[0]["public_opportunity"]["possible_duplicate_ids"]), 1)

    def test_different_confirmed_references_never_merge_on_title(self):
        data = self.raw()
        data["records"] = [copy.deepcopy(data["records"][1])]
        other = copy.deepcopy(data["records"][0])
        other.update(record_id="OTHER-REF", competition_ref="DEMO-COMP-DIFFERENT")
        data["records"].append(other)
        self.ingest(parse_source_batch(data))
        self.assertEqual(self.count("competitions"), 2)
        self.assertEqual(self.count("tasks"), 4)

    def test_conflicting_source_fields_are_visible_and_do_not_guess_new_owner(self):
        data = self.raw()
        data["records"][0]["opportunity"]["buyer_org_number"] = "000000505"
        self.ingest(parse_source_batch(data))
        task = self.selected()
        self.assertIn("buyer_org_number", task["public_opportunity"]["conflicts"])
        self.assertEqual(task["reason_code"], "DATA_KONFLIKT")
        self.assertIsNone(task["owner"])
        self.assertTrue(task["data_review_required"])

    def test_missing_update_values_do_not_erase_known_information(self):
        self.ingest(self.initial)
        data = self.raw()
        data["batch_id"] = "PARTIAL-UPDATE"
        data["read_until"] = {"doffin": "2026-10-14T09:00:00Z", "mercell": "2026-10-14T09:00:00Z"}
        for record in data["records"]:
            record["modified_at"] = "2026-10-14T08:30:00Z"
            record["opportunity"]["deadline"] = None
            record["opportunity"]["area"] = None
        self.ingest(parse_source_batch(data))
        task = self.selected()
        self.assertEqual(task["deadline"], "2026-11-20")
        self.assertEqual(task["area"], "Vest")

    def test_invalid_same_version_rolls_back_entire_batch_and_watermarks(self):
        self.ingest(self.initial)
        before = self.store.tasks(Channel.DIRECT)
        data = self.raw()
        data["batch_id"] = "INVALID-CONFLICT"
        new_record = copy.deepcopy(data["records"][2])
        new_record.update(record_id="NEW-BEFORE-FAILURE", competition_ref="NEW-BEFORE-FAILURE")
        conflicting = copy.deepcopy(data["records"][1])
        conflicting["opportunity"]["deadline"] = "2026-11-29"
        data["records"] = [new_record, conflicting]
        data["read_until"]["mercell"] = "2026-10-14T11:00:00Z"
        with self.assertRaises(DemoDataError):
            self.ingest(parse_source_batch(data))
        self.assertEqual(self.count("competitions"), 2)
        self.assertEqual(self.count("source_records"), 3)
        self.assertEqual(self.store.tasks(Channel.DIRECT), before)
        self.assertEqual(self.count("batches"), 1)
        through = self.store.connection.execute("SELECT read_until FROM sync_state WHERE source='mercell'").fetchone()[0]
        self.assertTrue(through.startswith("2026-10-14T08:00:00"))

    def test_ambiguous_source_identity_is_rejected_without_relinking(self):
        self.ingest(self.initial)
        data = self.raw("02-update.json")
        data["records"] = [data["records"][0]]
        data["records"][0]["competition_ref"] = "DEMO-COMP-102"
        with self.assertRaises(DemoDataError):
            self.ingest(parse_source_batch(data))
        self.assertEqual(self.count("source_versions"), 3)
        self.assertEqual(self.selected()["deadline"], "2026-11-20")

    def test_prior_batch_id_cannot_be_reused_for_different_content(self):
        self.ingest(self.initial)
        data = self.raw()
        data["description"] = "different batch content"
        with self.assertRaises(DemoDataError):
            self.ingest(parse_source_batch(data))

    def test_partner_task_and_history_do_not_include_direct_reassignment(self):
        self.ingest(self.initial)
        task = self.selected()
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"])
        self.ingest(self.batch("02-update.json"))
        serialized = json.dumps(self.store.tasks(Channel.INDIRECT))
        for private in ("D-01", "D-03", "Demo Anna", "Demo Nora", "INSTALLERT_BASE", "manuelt_omfordelt", "KUNDEEIER"):
            self.assertNotIn(private, serialized)

    def test_wrong_channel_task_or_person_cannot_be_reassigned(self):
        self.ingest(self.initial)
        task = self.selected()
        with self.assertRaises(DemoDataError):
            self.store.reassign(task["task_id"], Channel.INDIRECT, self.indirect.people["P-01"])
        with self.assertRaises(DemoDataError):
            self.store.reassign(task["task_id"], Channel.DIRECT, self.indirect.people["P-01"])
        with self.assertRaises(DemoDataError):
            self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-04"])
        self.assertEqual(self.selected()["owner"]["id"], "D-01")

    def test_cli_ingest_and_show_use_persistent_state(self):
        ingest = subprocess.run([sys.executable, "-m", "mission_distribution", "ingest",
                                 str(BATCHES / "01-initial.json"), "--db", str(self.path), "--json"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ingest.returncode, 0, ingest.stderr)
        self.assertEqual(json.loads(ingest.stdout)["report"]["created_tasks"], 4)
        show = subprocess.run([sys.executable, "-m", "mission_distribution", "tasks", "--channel", "indirekte",
                               "--db", str(self.path), "--json"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(show.returncode, 0, show.stderr)
        payload = json.loads(show.stdout)
        self.assertEqual(len(payload["tasks"]), 2)
        self.assertTrue(all(task["channel"] == "indirekte" for task in payload["tasks"]))

    def test_enrichment_resolves_unassigned_task_without_changing_task_id(self):
        data = self.raw()
        data["records"] = [data["records"][0]]
        self.ingest(parse_source_batch(data))
        original = self.selected(Channel.INDIRECT)
        self.assertIsNone(original["owner"])
        next_batch = self.raw()
        next_batch["batch_id"] = "ENRICHED-LATER"
        next_batch["records"] = [next_batch["records"][1]]
        self.ingest(parse_source_batch(next_batch))
        enriched = self.selected(Channel.INDIRECT)
        self.assertEqual(enriched["task_id"], original["task_id"])
        self.assertEqual(enriched["owner"]["id"], "P-01")

    def test_empty_successful_batch_advances_cursor_without_task_changes(self):
        self.ingest(self.initial)
        before = self.store.tasks(Channel.DIRECT)
        report = self.ingest(parse_source_batch({
            "synthetic": True, "batch_id": "EMPTY-WINDOW", "records": [],
            "read_until": {"doffin": "2026-10-14T12:00:00Z"},
        }))
        self.assertEqual(report["records_seen"], 0)
        self.assertEqual(self.store.tasks(Channel.DIRECT), before)
        through = self.store.connection.execute("SELECT read_until FROM sync_state WHERE source='doffin'").fetchone()[0]
        self.assertTrue(through.startswith("2026-10-14T12:00:00"))

    def test_nonunique_fallback_key_stays_separate(self):
        data = self.raw()
        data["records"] = [copy.deepcopy(data["records"][1])]
        other = copy.deepcopy(data["records"][0])
        other.update(record_id="OTHER-CONFIRMED", competition_ref="DEMO-COMP-OTHER")
        data["records"].append(other)
        self.ingest(parse_source_batch(data))
        incoming = copy.deepcopy(data)
        incoming["batch_id"] = "AMBIGUOUS-FALLBACK"
        incoming["records"] = [copy.deepcopy(data["records"][0])]
        incoming["records"][0].update(record_id="UNCONFIRMED", competition_ref=None)
        report = self.ingest(parse_source_batch(incoming))
        self.assertEqual(report["possible_duplicates"], 1)
        self.assertEqual(self.count("competitions"), 3)

    def test_lagging_source_conflict_keeps_existing_owner_but_requests_review(self):
        self.ingest(self.initial)
        data = self.raw("02-update.json")
        data["records"] = [data["records"][0]]
        self.ingest(parse_source_batch(data))
        task = self.selected()
        self.assertEqual(task["owner"]["id"], "D-01")
        self.assertEqual(task["deadline"], "2026-11-27")
        self.assertIn("deadline", task["public_opportunity"]["conflicts"])
        self.assertTrue(task["data_review_required"])

    def test_new_cancelled_competition_is_stored_without_new_sales_tasks(self):
        report = self.ingest(self.batch("03-cancelled.json"))
        self.assertEqual(report["created_competitions"], 1)
        self.assertEqual(report["created_tasks"], 0)
        self.assertEqual(self.count("tasks"), 0)

    def test_cli_manual_reassignment_is_preserved_by_cli_update(self):
        self.ingest(self.initial)
        reassign = subprocess.run([
            sys.executable, "-m", "mission_distribution", "reassign", "--channel", "direkte",
            "--competition-ref", "DEMO-COMP-101", "--person", "D-03", "--db", str(self.path), "--json",
        ], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(reassign.returncode, 0, reassign.stderr)
        self.assertEqual(json.loads(reassign.stdout)["task"]["owner"]["id"], "D-03")
        update = subprocess.run([
            sys.executable, "-m", "mission_distribution", "ingest", str(BATCHES / "02-update.json"),
            "--db", str(self.path), "--json",
        ], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(update.returncode, 0, update.stderr)
        self.assertEqual(self.selected()["owner"]["id"], "D-03")


class SourceBatchValidationTests(unittest.TestCase):
    def raw(self):
        return json.loads((BATCHES / "01-initial.json").read_text(encoding="utf-8"))

    def test_timezone_is_required(self):
        data = self.raw()
        data["records"][0]["modified_at"] = "2026-10-14T07:30:00"
        with self.assertRaises(DemoDataError):
            parse_source_batch(data)

    def test_record_after_read_boundary_is_rejected(self):
        data = self.raw()
        data["records"][0]["modified_at"] = "2026-10-14T09:30:00Z"
        with self.assertRaises(DemoDataError):
            parse_source_batch(data)

    def test_duplicate_source_id_in_one_batch_is_rejected(self):
        data = self.raw()
        data["records"].append(copy.deepcopy(data["records"][0]))
        with self.assertRaises(DemoDataError):
            parse_source_batch(data)

    def test_private_input_fields_are_not_copied_into_shared_source_payload(self):
        data = self.raw()
        data["records"][0]["opportunity"].update(owner_id="D-SECRET", installed_base=True, prior_contact_ids=["D-SECRET"])
        payload = parse_source_batch(data).records[0].payload
        self.assertNotIn("owner_id", payload)
        self.assertNotIn("installed_base", payload)
        self.assertNotIn("prior_contact_ids", payload)

    def test_dangerous_document_scheme_is_rejected(self):
        data = self.raw()
        data["records"][0]["opportunity"]["document_urls"] = ["javascript:alert(1)"]
        with self.assertRaises(DemoDataError):
            parse_source_batch(data)


if __name__ == "__main__":
    unittest.main()
