"""Exercise approval validity, stale pages and channel-local manual decisions."""

from dataclasses import replace
from html.parser import HTMLParser
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.parse import urlencode

from mission_distribution.approval import StaleProposalError, approval_current, review_revision
from mission_distribution.classification import load_classification_rules
from mission_distribution.dashboard import DashboardActions, DashboardQuery, render_dashboard, task_status
from mission_distribution.ingestion import ingest_batch
from mission_distribution.models import Channel, DemoDataError, load_direct_rules, load_indirect_rules
from mission_distribution.source_data import json_text, parse_source_batch
from mission_distribution.storage import DemoStore
from mission_distribution.web_server import create_server


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demo_data"


class ApprovalFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "demo.sqlite3"
        self.store = DemoStore(self.path)
        self.addCleanup(self.store.connection.close)
        self.direct = load_direct_rules(DATA / "direct_rules.json")
        self.indirect = load_indirect_rules(DATA / "indirect_rules.json")
        self.rules = load_classification_rules(DATA / "classification_rules.json")
        self.raw = json.loads((DATA / "source_batches" / "05-classification.json").read_text())
        self.update_index = 0
        self.ingest(self.raw)

    def ingest(self, raw):
        return ingest_batch(self.store, parse_source_batch(raw), self.direct, self.indirect, self.rules)

    def task(self, suffix="001", channel=Channel.DIRECT):
        return next(item for item in self.store.tasks(channel) if item["competition_ref"] == f"DEMO-FAG-COMP-{suffix}")

    def approve(self, suffix="001", channel=Channel.DIRECT, acknowledge_review=False):
        task = self.task(suffix, channel)
        people = self.direct.people if channel == Channel.DIRECT else self.indirect.people
        return self.store.approve(task["task_id"], channel, people,
                                  review_revision(task, task["public_opportunity"]), acknowledge_review)

    def update(self, **fields):
        self.update_index += 1
        raw = json.loads(json.dumps(self.raw))
        raw["batch_id"] += f"-change-{self.update_index}"
        for record in raw["records"]:
            if record["competition_ref"] == "DEMO-FAG-COMP-001":
                record["modified_at"] = f"2026-10-14T11:{30+self.update_index:02}:00Z"
                record["opportunity"].update(fields)
        return self.ingest(raw)

    def replace_public(self, **fields):
        task = self.task()
        public = task["public_opportunity"]
        public.update(fields)
        with self.store.connection:
            self.store.connection.execute("UPDATE competitions SET payload_json = ? WHERE id = ?",
                                          (json_text(public), task["competition_id"]))


class ApprovalTests(ApprovalFixture):
    def test_approval_is_persistent_channel_local_and_not_delivery(self):
        task = self.task()
        before_partner = self.store.tasks(Channel.INDIRECT)
        self.approve()
        with DemoStore(self.path) as reopened:
            approved = next(item for item in reopened.tasks(Channel.DIRECT) if item["task_id"] == task["task_id"])
            self.assertTrue(approval_current(approved, approved["public_opportunity"]))
            self.assertEqual(approved["delivery_status"], "ikke_levert")
            self.assertEqual(approved["approval"]["actor"], "lokal_demobruker")
            self.assertEqual(task_status(approved), "godkjent")
            self.assertEqual(reopened.tasks(Channel.INDIRECT), before_partner)

    def test_repeated_approval_does_not_duplicate_audit_events(self):
        self.approve()
        before = self.task()["events"]
        self.approve()
        self.assertEqual(self.task()["events"], before)

    def test_unknown_trade_can_be_approved_for_registered_customer_owner(self):
        self.approve("004")
        task = self.task("004")
        self.assertIsNone(task["main_trade"])
        self.assertEqual(task["owner"]["id"], "D-01")
        self.assertEqual(task_status(task), "godkjent")

    def test_unassigned_task_cannot_be_approved_until_person_is_chosen(self):
        with self.assertRaises(DemoDataError):
            self.approve("003")
        task = self.task("003")
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"],
                            review_revision(task, task["public_opportunity"]))
        self.assertNotIn("approval", self.task("003"))
        self.approve("003")
        self.assertEqual(task_status(self.task("003")), "godkjent")

    def test_inactive_current_owner_is_rejected_even_when_task_snapshot_says_active(self):
        task = self.task()
        people = {**self.direct.people, "D-01": replace(self.direct.people["D-01"], active=False)}
        with self.assertRaises(DemoDataError):
            self.store.approve(task["task_id"], Channel.DIRECT, people,
                               review_revision(task, task["public_opportunity"]))
        self.assertNotIn("approval", self.task())

    def test_wrong_channel_cannot_approve_or_change_another_channels_task(self):
        task = self.task()
        revision = review_revision(task, task["public_opportunity"])
        with self.assertRaises(DemoDataError):
            self.store.approve(task["task_id"], Channel.INDIRECT, self.indirect.people, revision)
        with self.assertRaises(DemoDataError):
            self.store.reassign(task["task_id"], Channel.DIRECT, self.indirect.people["P-01"], revision)
        self.assertNotIn("approval", self.task())

    def test_manual_change_invalidates_approval_without_changing_partner(self):
        self.approve()
        self.approve(channel=Channel.INDIRECT)
        partner = self.task(channel=Channel.INDIRECT)
        task = self.task()
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"],
                            review_revision(task, task["public_opportunity"]))
        changed = self.task()
        self.assertEqual(changed["approval"]["state"], "utdatert")
        self.assertEqual(task_status(changed), "ny_godkjenning")
        self.assertEqual(self.task(channel=Channel.INDIRECT), partner)
        self.approve()
        self.assertEqual(self.task()["approval"]["owner_id"], "D-03")

    def test_selecting_same_owner_preserves_approval_and_history(self):
        self.approve()
        task = self.task()
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-01"],
                            review_revision(task, task["public_opportunity"]))
        self.assertEqual(self.task(), task)

    def test_stale_approval_or_manual_form_is_rejected_without_overwriting(self):
        original = self.task()
        revision = review_revision(original, original["public_opportunity"])
        self.store.reassign(original["task_id"], Channel.DIRECT, self.direct.people["D-03"], revision)
        before = self.task()
        with self.assertRaises(StaleProposalError):
            self.store.approve(original["task_id"], Channel.DIRECT, self.direct.people, revision)
        with self.assertRaises(StaleProposalError):
            self.store.reassign(original["task_id"], Channel.DIRECT, self.direct.people["D-02"], revision)
        self.assertEqual(self.task(), before)

    def test_manual_form_from_before_approval_cannot_overwrite_new_approval(self):
        task = self.task()
        old = review_revision(task, task["public_opportunity"])
        self.approve()
        with self.assertRaises(StaleProposalError):
            self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"], old)
        self.assertEqual(task_status(self.task()), "godkjent")

    def test_old_form_stays_stale_when_owner_changes_away_and_back(self):
        task = self.task()
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"])
        snapshot = self.task()
        old = review_revision(snapshot, snapshot["public_opportunity"])
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-02"])
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"])
        with self.assertRaises(StaleProposalError):
            self.store.approve(task["task_id"], Channel.DIRECT, self.direct.people, old)

    def test_deadline_update_invalidates_both_approvals_and_keeps_ids_and_owners(self):
        for channel in Channel:
            self.approve(channel=channel)
        before = {channel: self.task(channel=channel) for channel in Channel}
        self.update(deadline="2026-12-08")
        for channel in Channel:
            task = self.task(channel=channel)
            self.assertEqual(task["task_id"], before[channel]["task_id"])
            self.assertEqual(task["owner"], before[channel]["owner"])
            self.assertEqual(task["approval"]["state"], "utdatert")
            self.assertIn("godkjenning_utdatert", [event["type"] for event in task["events"]])

    def test_new_source_version_without_field_changes_still_requires_new_review(self):
        self.approve()
        self.update()
        self.assertEqual(self.task()["approval"]["state"], "utdatert")

    def test_replaying_processed_batch_keeps_valid_approval(self):
        self.approve()
        before = self.task()
        self.ingest(self.raw)
        self.assertEqual(self.task(), before)

    def test_cancelled_task_cannot_be_reassigned_or_approved(self):
        self.approve()
        self.update(notice_status="cancelled")
        task = self.task()
        self.assertEqual(task["approval"]["state"], "utdatert")
        with self.assertRaises(DemoDataError):
            self.approve()
        with self.assertRaises(DemoDataError):
            self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"])

    def test_new_irrelevance_cannot_be_overridden_by_approval(self):
        self.update(title="Demo heis", description="Heis", main_cpv="50750000")
        with self.assertRaises(DemoDataError):
            self.approve(acknowledge_review=True)

    def test_conflicts_and_possible_duplicates_block_even_acknowledged_approval(self):
        for fields in ({"conflicts": {"main_cpv": [{"value": "x"}]}},
                       {"conflicts": {}, "possible_duplicate_ids": ["OTHER-DEMO"]}):
            self.replace_public(**fields)
            with self.subTest(fields=fields), self.assertRaises(DemoDataError):
                self.approve(acknowledge_review=True)

    def test_changed_trade_requires_explicit_review_and_can_be_approved_again(self):
        self.approve()
        self.update(main_cpv="50610000", title="Demo adgangskontroll", description="Service")
        self.assertTrue(self.task()["data_review_required"])
        with self.assertRaises(DemoDataError):
            self.approve()
        self.approve(acknowledge_review=True)
        task = self.task()
        self.assertFalse(task["data_review_required"])
        self.assertFalse(task["classification_review_required"])
        self.assertTrue(approval_current(task, task["public_opportunity"]))
        self.update(deadline="2026-12-08", main_cpv="50610000", title="Demo adgangskontroll", description="Service")
        self.assertFalse(self.task()["data_review_required"])

    def test_browser_forms_show_only_active_people_from_selected_channel(self):
        query = DashboardQuery(channel=Channel.INDIRECT, selected=self.task(channel=Channel.INDIRECT)["task_id"])
        actions = DashboardActions(tuple(self.direct.people.values()) + tuple(self.indirect.people.values()), "test-token")
        page = render_dashboard(self.store.tasks(Channel.INDIRECT), self.store.assessments(), query, actions)
        self.assertIn("/actions/reassign", page)
        self.assertIn("/actions/approve", page)
        for name in ("Demo Anna", "D-01", "P-04", "P-05"):
            self.assertNotIn(name, page)

    def test_approved_browser_view_says_local_not_delivery(self):
        self.approve()
        task = self.task()
        page = render_dashboard(self.store.tasks(Channel.DIRECT), self.store.assessments(),
                                DashboardQuery(selected=task["task_id"]), DashboardActions(tuple(self.direct.people.values()), "token"))
        self.assertIn("Godkjent lokalt", page)
        self.assertIn("lokal demobruker uten pålogging", page)
        self.assertIn("Ingen oppgave eller varsel er sendt", page)
        self.assertNotIn('action="/actions/approve"', page)

    def test_browser_warns_if_already_approved_owner_is_now_inactive(self):
        self.approve()
        task = self.task()
        people = tuple(replace(person, active=False) if person.id == "D-01" else person
                       for person in self.direct.people.values())
        page = render_dashboard(self.store.tasks(Channel.DIRECT), self.store.assessments(),
                                DashboardQuery(selected=task["task_id"]), DashboardActions(people, "token"))
        self.assertIn("Mottakeren er ikke aktiv", page)
        self.assertNotIn('class="approval-confirmed"', page)


class FormParser(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.forms = {}
        self.current = None
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = attrs.get("action")
            self.forms[self.current] = {}
        elif tag == "input" and self.current and attrs.get("type") == "hidden":
            self.forms[self.current][attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


class ApprovalHttpTests(ApprovalFixture):
    def setUp(self):
        super().setUp()
        self.rules_directory = Path(self.directory.name) / "rules"
        self.rules_directory.mkdir()
        for filename in ("direct_rules.json", "indirect_rules.json"):
            (self.rules_directory / filename).write_text((DATA / filename).read_text())
        self.server = create_server(self.path, 0, self.rules_directory)
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, body=None, headers=None):
        client = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            client.request(method, path, body=body, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            client.close()

    def forms(self, suffix="001", channel=Channel.DIRECT):
        task = self.task(suffix, channel)
        status, _, html = self.request("GET", "/?" + urlencode({"channel": channel.value, "task": task["task_id"]}))
        self.assertEqual(status, 200)
        return FormParser(html).forms

    def post(self, action, fields, headers=None):
        default = {"Content-Type": "application/x-www-form-urlencoded",
                   "Origin": f"http://127.0.0.1:{self.server.server_port}"}
        default.update(headers or {})
        return self.request("POST", action, urlencode(fields), default)

    def test_browser_manual_choice_then_approval_persists_without_delivery(self):
        fields = self.forms("003")["/actions/reassign"]
        status, headers, _ = self.post("/actions/reassign", {**fields, "person_id": "D-03"})
        self.assertEqual(status, 303)
        self.assertIn("channel=direkte", headers["Location"])
        self.assertNotIn("approval", self.task("003"))
        fields = self.forms("003")["/actions/approve"]
        self.assertEqual(self.post("/actions/approve", fields)[0], 303)
        status, _, page = self.request("GET", headers["Location"])
        self.assertEqual(status, 200)
        self.assertIn("Godkjent lokalt", page)
        self.assertEqual(self.task("003")["delivery_status"], "ikke_levert")
        self.assertIsNone(self.task("003", Channel.INDIRECT)["owner"])

    def test_missing_or_wrong_csrf_origin_and_host_do_not_change_tasks(self):
        fields = self.forms()["/actions/approve"]
        before = self.task()
        for token in ("wrong", "æ", ""):
            self.assertEqual(self.post("/actions/approve", {**fields, "csrf_token": token})[0], 403)
        missing = {key: value for key, value in fields.items() if key != "csrf_token"}
        self.assertEqual(self.post("/actions/approve", missing)[0], 400)
        self.assertEqual(self.post("/actions/approve", fields, {"Origin": "https://foreign.example"})[0], 403)
        self.assertEqual(self.post("/actions/approve", fields, {"Host": "foreign.example"})[0], 403)
        self.assertEqual(self.task(), before)

    def test_cross_channel_person_task_and_inactive_person_are_rejected(self):
        fields = self.forms()["/actions/reassign"]
        before = self.task()
        for person in ("P-01", "D-04", "missing"):
            self.assertEqual(self.post("/actions/reassign", {**fields, "person_id": person})[0], 400)
        fields["task_id"] = self.task(channel=Channel.INDIRECT)["task_id"]
        self.assertEqual(self.post("/actions/reassign", {**fields, "person_id": "D-03"})[0], 400)
        self.assertEqual(self.task(), before)

    def test_stale_browser_form_is_rejected_after_new_source_data(self):
        old = self.forms()["/actions/approve"]
        self.update(deadline="2026-12-08")
        self.assertEqual(self.post("/actions/approve", old)[0], 409)
        self.assertNotIn("approval", self.task())
        fresh = self.forms()["/actions/approve"]
        self.assertEqual(self.post("/actions/approve", fresh)[0], 303)

    def test_browser_review_checkbox_is_enforced_on_server(self):
        self.update(main_cpv="50610000", title="Demo adgangskontroll", description="Service")
        fields = self.forms()["/actions/approve"]
        self.assertEqual(self.post("/actions/approve", fields)[0], 400)
        self.assertEqual(self.post("/actions/approve", {**fields, "acknowledge_review": "yes"})[0], 303)
        self.assertEqual(task_status(self.task()), "godkjent")

    def test_inactivated_person_after_page_load_cannot_be_approved(self):
        fields = self.forms()["/actions/approve"]
        path = self.rules_directory / "direct_rules.json"
        rules = json.loads(path.read_text())
        next(person for person in rules["people"] if person["id"] == "D-01")["active"] = False
        path.write_text(json.dumps(rules))
        self.assertEqual(self.post("/actions/approve", fields)[0], 400)
        self.assertNotIn("approval", self.task())

    def test_get_and_repeated_post_do_not_duplicate_approval_events(self):
        fields = self.forms()["/actions/approve"]
        self.assertEqual(self.post("/actions/approve", fields)[0], 303)
        before = self.task()
        self.assertEqual(self.post("/actions/approve", fields)[0], 303)
        self.forms()
        self.assertEqual(self.task(), before)

    def test_invalid_content_type_duplicate_fields_and_oversized_body_are_rejected(self):
        fields = self.forms()["/actions/approve"]
        before = self.task()
        self.assertEqual(self.post("/actions/approve", fields, {"Content-Type": "application/json"})[0], 400)
        duplicate = list(fields.items()) + [("channel", "indirekte")]
        self.assertEqual(self.post("/actions/approve", duplicate)[0], 400)
        status, _, _ = self.request("POST", "/actions/approve", "x=" + "x" * 9000,
                                     {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 400)
        self.assertEqual(self.task(), before)


if __name__ == "__main__":
    unittest.main()
