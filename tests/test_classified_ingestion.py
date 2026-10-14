"""Verify that classification gates routing without losing audit or task identity."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mission_distribution.classification import load_classification_rules
from mission_distribution.ingestion import ingest_batch
from mission_distribution.models import Channel, DemoDataError, load_direct_rules, load_indirect_rules
from mission_distribution.source_data import load_source_batch, parse_source_batch
from mission_distribution.storage import DemoStore


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demo_data"
FILENAME = DATA / "source_batches" / "05-classification.json"


class ClassifiedIngestionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "demo.sqlite3"
        self.store = DemoStore(self.path)
        self.addCleanup(self.store.connection.close)
        self.rules = load_classification_rules(DATA / "classification_rules.json")
        self.direct = load_direct_rules(DATA / "direct_rules.json")
        self.indirect = load_indirect_rules(DATA / "indirect_rules.json")
        self.raw = json.loads(FILENAME.read_text())

    def ingest(self, raw=None):
        return ingest_batch(self.store, parse_source_batch(raw or self.raw), self.direct, self.indirect, self.rules)

    def selected(self, suffix="001", channel=Channel.DIRECT):
        return next(task for task in self.store.tasks(channel) if task["competition_ref"] == f"DEMO-FAG-COMP-{suffix}")

    def count(self, table):
        return self.store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def single(self, suffix="001"):
        raw = copy.deepcopy(self.raw)
        raw["records"] = [next(record for record in raw["records"]
                               if record["source"] == "doffin" and record["competition_ref"] == f"DEMO-FAG-COMP-{suffix}")]
        raw["records"][0]["opportunity"]["buyer_org_number"] = "000000101"
        return raw

    def update(self, raw, **changes):
        updated = copy.deepcopy(raw)
        updated["batch_id"] += "-update"
        for record in updated["records"]:
            record["modified_at"] = "2026-10-14T11:30:00Z"
            record["opportunity"].update(changes)
        return updated

    def test_pipeline_derives_trade_and_area_then_routes(self):
        report = self.ingest()
        self.assertEqual(report["records_seen"], 9)
        self.assertEqual(report["created_competitions"], 8)
        self.assertEqual(report["created_tasks"], 12)
        self.assertEqual(report["not_relevant_competitions"], 2)
        task = self.selected()
        self.assertEqual(task["owner"]["id"], "D-01")
        self.assertEqual(task["main_trade"], "BA")
        self.assertEqual(task["area"], "Vest")
        public = task["public_opportunity"]
        self.assertEqual(public["field_origins"]["main_trade"]["method"], "regeltabell")
        self.assertEqual(len(public["source_refs"]), 2)
        self.assertEqual(public["classification"]["rules_fingerprint"], self.rules.fingerprint)

    def test_irrelevant_is_saved_with_evidence_but_no_new_tasks(self):
        raw = self.single("005")
        report = self.ingest(raw)
        self.assertEqual(report["created_tasks"], 0)
        row = self.store.connection.execute("SELECT payload_json FROM competitions").fetchone()
        result = json.loads(row["payload_json"])["classification"]
        self.assertEqual(result["excluded_codes"], ["50750000"])
        self.assertFalse(result["should_route"])

    def test_broad_code_still_reaches_customer_owner_partner_needs_trade(self):
        self.ingest()
        self.assertEqual(self.selected("004")["owner"]["id"], "D-01")
        partner = self.selected("004", Channel.INDIRECT)
        self.assertIsNone(partner["owner"])
        self.assertEqual(partner["reason_code"], "FAG_UKJENT")

    def test_replay_does_not_duplicate_tasks_or_history(self):
        self.ingest()
        original = self.store.tasks(Channel.DIRECT)
        report = self.ingest()
        self.assertTrue(report["already_processed"])
        self.assertEqual(self.store.tasks(Channel.DIRECT), original)
        self.assertEqual(self.count("tasks"), 12)

    def test_rules_required_and_failed_ingestion_is_rolled_back(self):
        with self.assertRaises(DemoDataError):
            ingest_batch(self.store, load_source_batch(FILENAME), self.direct, self.indirect)
        for table in ("competitions", "tasks", "source_records", "sync_state", "batches"):
            self.assertEqual(self.count(table), 0)

    def test_rules_mode_rejects_manual_trade_or_area(self):
        for field, value in [("main_trade", "BA"), ("other_trades", ["FS"]), ("area", "Vest")]:
            raw = self.single()
            raw["records"][0]["opportunity"][field] = value
            with self.subTest(field=field), self.assertRaises(DemoDataError):
                parse_source_batch(raw)

    def test_legacy_batch_does_not_acquire_new_payload_fields(self):
        batch = load_source_batch(DATA / "source_batches" / "01-initial.json")
        self.assertNotIn("classification_input", batch.records[0].payload)
        report = ingest_batch(self.store, batch, self.direct, self.indirect, self.rules)
        self.assertEqual(report["created_tasks"], 4)
        self.assertNotIn("classification", self.store.tasks(Channel.DIRECT)[0]["public_opportunity"])

    def test_conflicting_cpv_requires_review_even_when_selected_code_has_no_hit(self):
        raw = self.single()
        second = copy.deepcopy(raw["records"][0])
        second.update(source="mercell", record_id="CONFLICT-CODE", modified_at="2026-10-14T11:10:00Z")
        second["opportunity"].update(main_cpv="50750000", title="Demo heis", description="Heis")
        raw["records"].append(second)
        self.ingest(raw)
        task = self.selected()
        self.assertFalse(task["public_opportunity"]["classification"]["should_route"])
        self.assertIn("main_cpv", task["public_opportunity"]["conflicts"])
        self.assertEqual(task["reason_code"], "DATA_KONFLIKT")
        self.assertIsNone(task["owner"])

    def test_later_irrelevant_update_keeps_task_and_manual_owner_requests_review(self):
        raw = self.single()
        self.ingest(raw)
        original = self.selected()
        self.store.reassign(original["task_id"], Channel.DIRECT, self.direct.people["D-03"])
        changed = self.update(raw, main_cpv="50750000", title="Demo: heis", description="Oppdiktet heisarbeid")
        self.ingest(changed)
        task = self.selected()
        self.assertEqual(task["task_id"], original["task_id"])
        self.assertEqual(task["owner"]["id"], "D-03")
        self.assertTrue(task["data_review_required"])
        self.assertEqual(task["public_opportunity"]["classification"]["relevance"], "ikke_relevant")
        self.assertIn("fagvurdering_endret", [event["type"] for event in task["events"]])

    def test_later_relevant_update_can_create_first_tasks(self):
        raw = self.single("005")
        self.ingest(raw)
        report = self.ingest(self.update(raw, main_cpv="50700000", title="Demo SD-anlegg", description="Service"))
        self.assertEqual(report["created_competitions"], 0)
        self.assertEqual(report["created_tasks"], 2)
        self.assertEqual(self.selected("005")["owner"]["id"], "D-01")

    def test_changed_trade_keeps_owner_and_review_survives_unrelated_update(self):
        raw = self.single()
        self.ingest(raw)
        changed = self.update(raw, main_cpv="50610000", title="Demo adgangskontroll", description="Service")
        self.ingest(changed)
        task = self.selected()
        self.assertEqual(task["owner"]["id"], "D-01")
        self.assertEqual(task["main_trade"], "SE")
        self.assertTrue(task["data_review_required"])
        again = copy.deepcopy(changed)
        again["batch_id"] += "-deadline"
        again["records"][0]["modified_at"] = "2026-10-14T11:45:00Z"
        again["records"][0]["opportunity"]["deadline"] = "2026-12-03"
        self.ingest(again)
        self.assertTrue(self.selected()["data_review_required"])

    def test_partner_results_do_not_acquire_customer_private_metadata(self):
        self.ingest()
        output = json.dumps(self.store.tasks(Channel.INDIRECT))
        for private in ("INSTALLERT_BASE", "D-01", "prior_contact_ids", "customer_owner"):
            self.assertNotIn(private, output)
        self.assertIn("cpv_og_nokkelord", output)

    def test_cli_shows_discarded_assessments_without_allocations(self):
        command = [sys.executable, "-m", "mission_distribution"]
        result = subprocess.run(command + ["ingest", str(FILENAME), "--db", str(self.path), "--json"],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["report"]["created_tasks"], 12)
        result = subprocess.run(command + ["assessments", "--db", str(self.path), "--json"],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        assessments = json.loads(result.stdout)["assessments"]
        self.assertEqual(len(assessments), 8)
        self.assertEqual(sum(not item["classification"]["should_route"] for item in assessments), 2)
        self.assertNotIn("owner", result.stdout)
        result = subprocess.run(command + ["tasks", "--channel", "direkte", "--db", str(self.path)],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertIn("CPV 50700000 → BA", result.stdout)


if __name__ == "__main__":
    unittest.main()
