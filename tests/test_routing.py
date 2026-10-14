"""Check customer priority, absence, uncertainty, and partner-only decisions."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import unittest

from mission_distribution.models import Capacity, load_direct_rules, load_indirect_rules, load_opportunities
from mission_distribution.routing import route_direct, route_indirect


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demo_data"


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.opportunities = {item.id: item for item in load_opportunities(DATA / "opportunities.json")}
        cls.direct = load_direct_rules(DATA / "direct_rules.json")
        cls.indirect = load_indirect_rules(DATA / "indirect_rules.json")

    def test_all_demonstration_outcomes(self):
        expected = {
            "DEMO-001": ("D-01", "KUNDEEIER", "P-01", "FAG_OMRÅDE"),
            "DEMO-002": ("D-01", "KUNDEEIER", None, "FAG_UKJENT"),
            "DEMO-003": ("D-05", "FAG_OMRÅDE_VIKAR", "P-03", "FAG_OMRÅDE"),
            "DEMO-004": (None, "MULIG_KUNDE", None, "INGEN_REGEL"),
            "DEMO-005": (None, "OMRÅDE_UKJENT", None, "OMRÅDE_UKJENT"),
            "DEMO-006": (None, "EIER_INAKTIV", None, "EIER_INAKTIV"),
            "DEMO-007": ("D-03", "FAG_OMRÅDE", "P-01", "FAG_OMRÅDE"),
            "DEMO-008": (None, "EIER_INAKTIV", "P-01", "FAG_OMRÅDE"),
            "DEMO-009": (None, "INGEN_REGEL", None, "INGEN_REGEL"),
            "DEMO-010": ("D-07", "KUNDEEIER", "P-01", "FAG_OMRÅDE"),
        }
        for oid, values in expected.items():
            with self.subTest(opportunity=oid):
                direct = route_direct(self.opportunities[oid], self.direct)
                indirect = route_indirect(self.opportunities[oid], self.indirect)
                actual = (direct.owner.id if direct.owner else None, direct.reason_code,
                          indirect.owner.id if indirect.owner else None, indirect.reason_code)
                self.assertEqual(actual, values)

    def test_customer_owner_overrides_trade_area_owner(self):
        self.assertEqual(self.direct.coverage[("BA", "Vest")].owner_id, "D-03")
        decision = route_direct(self.opportunities["DEMO-001"], self.direct)
        self.assertEqual(decision.owner.id, "D-01")

    def test_customer_owner_can_receive_unknown_trade_and_area(self):
        opportunity = replace(self.opportunities["DEMO-002"], area=None)
        self.assertEqual(route_direct(opportunity, self.direct).owner.id, "D-01")

    def test_active_customer_deputy_is_used(self):
        people = dict(self.direct.people)
        people["D-01"] = replace(people["D-01"], active=False)
        decision = route_direct(self.opportunities["DEMO-001"], replace(self.direct, people=people))
        self.assertEqual((decision.owner.id, decision.reason_code), ("D-02", "KUNDEVIKAR"))

    def test_customer_with_no_dedicated_owner_uses_coverage(self):
        customers = dict(self.direct.customers)
        customers["000000101"] = replace(customers["000000101"], owner_id=None, deputy_id=None)
        decision = route_direct(self.opportunities["DEMO-001"], replace(self.direct, customers=customers))
        self.assertEqual(decision.owner.id, "D-03")

    def test_no_deputy_fallback_is_flagged(self):
        self.assertIn("EIER_INAKTIV", route_direct(self.opportunities["DEMO-007"], self.direct).flags)
        self.assertNotIn("EIER_INAKTIV", route_indirect(self.opportunities["DEMO-007"], self.indirect).flags)

    def test_partner_uses_active_deputy(self):
        people = dict(self.indirect.people)
        people["P-01"] = replace(people["P-01"], active=False)
        decision = route_indirect(self.opportunities["DEMO-001"], replace(self.indirect, people=people))
        self.assertEqual((decision.owner.id, decision.reason_code), ("P-02", "FAG_OMRÅDE_VIKAR"))

    def test_partner_output_does_not_include_direct_private_fields(self):
        opportunity = self.opportunities["DEMO-001"]
        self.assertIn("INSTALLERT_BASE", route_direct(opportunity, self.direct).flags)
        payload = route_indirect(opportunity, self.indirect).to_dict()
        self.assertEqual(payload["flags"], ["MERKENAVN"])
        serialized = json.dumps(payload)
        for private in ("INSTALLERT_BASE", "KUNDEEIER", "D-01", "Demo Anna", "customers"):
            self.assertNotIn(private, serialized)

    def test_unresolved_output_contains_no_owner_and_is_not_delivered(self):
        payload = route_indirect(self.opportunities["DEMO-004"], self.indirect).to_dict()
        self.assertEqual(payload["status"], "uavklart")
        self.assertIsNone(payload["owner"])
        self.assertEqual(payload["delivery_status"], "ikke_levert")

    def test_proposal_is_not_claimed_as_delivered(self):
        payload = route_direct(self.opportunities["DEMO-001"], self.direct).to_dict()
        self.assertEqual(payload["status"], "foreslått")
        self.assertEqual(payload["delivery_status"], "ikke_levert")

    def test_cli_json_is_parseable_and_selects_one_scenario(self):
        result = subprocess.run([sys.executable, "-m", "mission_distribution", "--channel", "indirekte",
                                 "--scenario", "DEMO-001", "--json"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["synthetic"])
        self.assertFalse(payload["external_services_called"])
        self.assertEqual(len(payload["decisions"]), 1)
        self.assertEqual(payload["decisions"][0]["owner"]["id"], "P-01")

    def test_cli_rejects_unknown_scenario_instead_of_showing_all(self):
        result = subprocess.run([sys.executable, "-m", "mission_distribution", "--channel", "direkte",
                                 "--scenario", "MISSING"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("DEMO-001:", result.stdout)

    def test_partner_terminal_output_hides_direct_context(self):
        result = subprocess.run([sys.executable, "-m", "mission_distribution", "--channel", "indirekte"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for private in ("INSTALLERT_BASE", "KUNDEEIER", "Demo Anna", "D-01", "kundeeier", "Direkte salg"):
            self.assertNotIn(private, result.stdout)

    def test_direct_terminal_output_hides_partner_context(self):
        result = subprocess.run([sys.executable, "-m", "mission_distribution", "--channel", "direkte"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for private in ("Demo Liv", "P-01", "Partnerkanalen"):
            self.assertNotIn(private, result.stdout)

    def test_matching_person_trade_does_not_replace_missing_coverage(self):
        self.assertIn("SE", self.direct.people["D-02"].trade_codes)
        decision = route_direct(self.opportunities["DEMO-009"], self.direct)
        self.assertIsNone(decision.owner)
        self.assertEqual(decision.reason_code, "INGEN_REGEL")

    def test_prior_contact_does_not_override_registered_customer_owner(self):
        customer = self.direct.customers["000000104"]
        self.assertEqual(customer.prior_contact_ids, ("D-08",))
        decision = route_direct(self.opportunities["DEMO-010"], self.direct)
        self.assertEqual(decision.owner.id, "D-07")

    def test_prior_contact_without_owner_does_not_bypass_coverage(self):
        customers = dict(self.direct.customers)
        customers["000000104"] = replace(customers["000000104"], owner_id=None, deputy_id=None)
        decision = route_direct(self.opportunities["DEMO-010"], replace(self.direct, customers=customers))
        self.assertEqual((decision.owner.id, decision.reason_code), ("D-03", "FAG_OMRÅDE"))

    def test_busy_owner_is_explicitly_a_proposal_without_capacity_routing(self):
        decision = route_direct(self.opportunities["DEMO-010"], self.direct)
        payload = decision.to_dict()
        self.assertTrue(payload["owner"]["active"])
        self.assertEqual(payload["owner"]["capacity"], "opptatt")
        self.assertFalse(payload["capacity_used_for_routing"])
        self.assertEqual(payload["status"], "foreslått")
        self.assertEqual(payload["delivery_status"], "ikke_levert")

    def test_customer_ownership_can_differ_from_person_trade_profile(self):
        decision = route_direct(self.opportunities["DEMO-010"], self.direct)
        self.assertEqual(decision.trade, "BA")
        self.assertEqual(decision.owner.trade_codes, ("FS",))
        self.assertEqual(decision.reason_code, "KUNDEEIER")

    def test_changing_capacity_does_not_silently_change_ownership_rule(self):
        people = dict(self.direct.people)
        people["D-07"] = replace(people["D-07"], capacity=Capacity.AVAILABLE)
        decision = route_direct(self.opportunities["DEMO-010"], replace(self.direct, people=people))
        self.assertEqual((decision.owner.id, decision.reason_code), ("D-07", "KUNDEEIER"))

    def test_partner_output_excludes_customer_contact_and_owner_metadata(self):
        payload = route_indirect(self.opportunities["DEMO-010"], self.indirect).to_dict()
        serialized = json.dumps(payload)
        for private in ("D-07", "D-08", "Demo Vera", "Demo Jonas", "prior_contact_ids", "KUNDEEIER",
                        "tidligere kontakt", "opptatt"):
            self.assertNotIn(private, serialized)

    def test_cli_explains_capacity_limit_for_busy_customer_owner(self):
        result = subprocess.run([sys.executable, "-m", "mission_distribution", "--channel", "direkte",
                                 "--scenario", "DEMO-010"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Demo Vera (D-07)", result.stdout)
        self.assertIn("Mottakers fagtilhørighet: FS", result.stdout)
        self.assertIn("Mottakers kapasitet: opptatt", result.stdout)
        self.assertIn("ikke brukt i fordelingen", result.stdout)
        self.assertNotIn("Demo Jonas", result.stdout)


if __name__ == "__main__":
    unittest.main()
