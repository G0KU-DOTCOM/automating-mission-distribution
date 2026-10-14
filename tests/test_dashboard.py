"""Check read-only views, channel boundaries, escaping and real HTTP requests."""

import ast
import copy
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from mission_distribution.classification import load_classification_rules
from mission_distribution.dashboard import DashboardQuery, filter_tasks, render_dashboard, task_status
from mission_distribution.ingestion import ingest_batch
from mission_distribution.models import Channel, DemoDataError, load_direct_rules, load_indirect_rules
from mission_distribution.source_data import load_source_batch, parse_source_batch
from mission_distribution.storage import DemoStore
from mission_distribution.web_server import create_server


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demo_data"


class DashboardFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "demo.sqlite3"
        self.store = DemoStore(self.path)
        self.addCleanup(self.store.connection.close)
        self.direct = load_direct_rules(DATA / "direct_rules.json")
        self.indirect = load_indirect_rules(DATA / "indirect_rules.json")
        ingest_batch(self.store, load_source_batch(DATA / "source_batches" / "05-classification.json"),
                     self.direct, self.indirect, load_classification_rules(DATA / "classification_rules.json"))

    def page(self, query=None):
        query = query or DashboardQuery()
        return render_dashboard(self.store.tasks(query.channel), self.store.assessments(), query)

    def selected(self, suffix, channel=Channel.DIRECT):
        return next(task for task in self.store.tasks(channel) if task["competition_ref"] == f"DEMO-FAG-COMP-{suffix}")


class DashboardTests(DashboardFixture):
    def test_direct_view_explains_customer_priority_and_unknown_trade(self):
        task = self.selected("004")
        page = self.page(DashboardQuery(selected=task["task_id"]))
        self.assertIn("Demo Anna", page)
        self.assertIn("KUNDEEIER", page)
        self.assertIn("45310000", page)
        self.assertIn("Ikke oppgitt: hovedfag", page)
        self.assertEqual(task_status(task), "forslag")
        self.assertIn("Ingen oppgaver er sendt", page)

    def test_partner_view_never_contains_customer_owner_or_direct_flags(self):
        task = self.selected("001", Channel.INDIRECT)
        page = self.page(DashboardQuery(channel=Channel.INDIRECT, selected=task["task_id"]))
        for private in ("Demo Anna", "D-01", "INSTALLERT_BASE", "Installert base", "KUNDEEIER"):
            self.assertNotIn(private, page)
        self.assertIn("Demo Liv", page)
        self.assertIn("Hoved-CPV 50700000", page)

    def test_mixed_input_cannot_render_another_channel(self):
        mixed = self.store.tasks(Channel.DIRECT) + self.store.tasks(Channel.INDIRECT)
        page = render_dashboard(mixed, self.store.assessments(), DashboardQuery(channel=Channel.INDIRECT))
        self.assertNotIn("Demo Anna", page)
        self.assertNotIn("Installert base", page)

    def test_cross_channel_task_identifier_is_rejected_without_details(self):
        direct_id = self.selected("001")["task_id"]
        with self.assertRaises(DemoDataError):
            self.page(DashboardQuery(channel=Channel.INDIRECT, selected=direct_id))

    def test_search_matches_buyer_and_owner_case_insensitively(self):
        tasks = self.store.tasks(Channel.DIRECT)
        result = filter_tasks(tasks, DashboardQuery(search="DEMO ANNA"))
        self.assertEqual({task["competition_ref"] for task in result}, {"DEMO-FAG-COMP-001", "DEMO-FAG-COMP-004"})
        result = filter_tasks(tasks, DashboardQuery(search="Aurora"))
        self.assertEqual(len(result), 2)

    def test_status_filter_distinguishes_unassigned_from_missing_trade(self):
        result = filter_tasks(self.store.tasks(Channel.DIRECT), DashboardQuery(status="uavklart"))
        self.assertEqual({task["competition_ref"] for task in result}, {"DEMO-FAG-COMP-003", "DEMO-FAG-COMP-008"})

    def test_cancelled_has_priority_over_owner_and_data_review_status(self):
        task = copy.deepcopy(self.selected("001"))
        task.update(lifecycle="avlyst", data_review_required=True)
        self.assertEqual(task_status(task), "avlyst")

    def test_unknown_deadlines_sort_last(self):
        tasks = copy.deepcopy(self.store.tasks(Channel.DIRECT)[:2])
        tasks[0]["deadline"] = None
        tasks[1]["deadline"] = "2026-12-01"
        self.assertEqual(filter_tasks(tasks, DashboardQuery())[0]["task_id"], tasks[1]["task_id"])

    def test_markup_and_search_are_escaped_and_unsafe_links_are_not_rendered(self):
        tasks = copy.deepcopy(self.store.tasks(Channel.DIRECT))
        tasks[0]["title"] = '<script>alert("x")</script>'
        tasks[0]["public_opportunity"]["opportunity"]["document_urls"] = ['javascript:alert(1)']
        page = render_dashboard(tasks, [], DashboardQuery(selected=tasks[0]["task_id"]))
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("javascript:", page)
        page = render_dashboard(tasks, [], DashboardQuery(search='"><script>'))
        self.assertIn("&quot;&gt;&lt;script&gt;", page)

    def test_empty_search_has_helpful_message(self):
        self.assertIn("Ingen oppgaver passer søket", self.page(DashboardQuery(search="not-present")))
        self.assertIn("Ingen oppgaver er lest inn ennå", render_dashboard([], [], DashboardQuery()))

    def test_discarded_public_assessments_are_visible_without_new_tasks(self):
        page = self.page()
        self.assertIn("Bortsorterte konkurranser", page)
        self.assertIn("Demo: kontorrekvisita", page)
        self.assertIn("Demo: service på heis", page)
        self.assertEqual(len(self.store.tasks(Channel.DIRECT)), 6)

    def test_manual_assignment_and_later_history_appear_only_in_own_view(self):
        task = self.selected("001")
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"])
        page = self.page(DashboardQuery(selected=task["task_id"]))
        self.assertIn("MANUELL_TILDELING", page)
        self.assertIn("D-01 → D-03", page)
        partner_page = self.page(DashboardQuery(channel=Channel.INDIRECT))
        self.assertNotIn("MANUELL_TILDELING", partner_page)
        self.assertNotIn("D-01 → D-03", partner_page)

    def test_deadline_update_preserves_manual_owner_and_renders_history(self):
        task = self.selected("001")
        self.store.reassign(task["task_id"], Channel.DIRECT, self.direct.people["D-03"])
        raw = json.loads((DATA / "source_batches" / "05-classification.json").read_text())
        raw["batch_id"] += "-new-deadline"
        for record in raw["records"]:
            record["modified_at"] = "2026-10-14T11:50:00Z"
            record["opportunity"]["deadline"] = "2026-12-08"
        ingest_batch(self.store, parse_source_batch(raw), self.direct, self.indirect,
                     load_classification_rules(DATA / "classification_rules.json"))
        page = self.page(DashboardQuery(selected=task["task_id"]))
        self.assertIn("Demo Nora", page)
        self.assertIn("MANUELL_TILDELING", page)
        self.assertIn("Tilbudsfrist endret: 01.12.2026 → 08.12.2026", page)
        self.assertEqual(self.selected("001")["task_id"], task["task_id"])

    def test_query_rejects_ambiguous_channels_or_unexpected_parameters(self):
        for params in ({"channel": ["other"]}, {"channel": ["direkte", "indirekte"]},
                       {"db": ["private.sqlite3"]}, {"status": ["sendt"]}, {"q": ["x" * 201]}):
            with self.subTest(params=params), self.assertRaises(DemoDataError):
                DashboardQuery.parse(params)

    def test_read_views_do_not_change_tasks_or_events(self):
        before = self.store.tasks(Channel.DIRECT)
        self.page()
        self.page(DashboardQuery(channel=Channel.INDIRECT))
        self.assertEqual(self.store.tasks(Channel.DIRECT), before)

    def test_new_modules_parse_with_python_311_syntax(self):
        for name in ("dashboard.py", "web_server.py"):
            ast.parse((ROOT / "mission_distribution" / name).read_text(), feature_version=(3, 11))


class DashboardHttpTests(DashboardFixture):
    def test_http_serves_page_and_assets_without_mutating_tasks(self):
        server = create_server(self.path, 0)
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        try:
            client = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            before = self.store.tasks(Channel.DIRECT)
            client.request("GET", "/?channel=indirekte")
            response = client.getresponse()
            self.assertEqual(response.status, 200)
            page = response.read().decode()
            self.assertIn("Partnerkanalen", page)
            self.assertNotIn("Demo Anna", page)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            self.assertEqual(response.getheader("Referrer-Policy"), "same-origin")
            self.assertIn("default-src 'none'", response.getheader("Content-Security-Policy"))
            client.request("GET", "/assets/dashboard.css")
            response = client.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("text/css", response.getheader("Content-Type"))
            response.read()
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                client.request(method, "/")
                response = client.getresponse()
                self.assertEqual(response.status, 405)
                response.read()
            direct_id = self.selected("001")["task_id"]
            client.request("GET", f"/?channel=indirekte&task={direct_id}")
            response = client.getresponse()
            self.assertEqual(response.status, 400)
            self.assertNotIn("Demo Anna", response.read().decode())
            for target in ("/assets/../../README.md", "/database.sqlite3", "/?channel=other"):
                client.request("GET", target)
                response = client.getresponse()
                self.assertIn(response.status, (400, 404))
                response.read()
            client.request("GET", "/", headers={"Host": "foreign.example"})
            response = client.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            self.assertEqual(self.store.tasks(Channel.DIRECT), before)
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
