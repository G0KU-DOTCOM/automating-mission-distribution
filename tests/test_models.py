"""Reject responsibility data that would silently produce incorrect routing."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from mission_distribution.models import Capacity, DemoDataError, load_direct_rules, load_indirect_rules, load_opportunities


DATA = Path(__file__).resolve().parents[1] / "demo_data"


class DemoInputTests(unittest.TestCase):
    def check_rejected(self, filename, mutate, loader):
        payload = json.loads((DATA / filename).read_text(encoding="utf-8"))
        mutate(payload)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / filename
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(DemoDataError):
                loader(path)

    def test_demo_records_and_responsibilities_load(self):
        self.assertEqual(len(load_opportunities(DATA / "opportunities.json")), 10)
        self.assertEqual(len(load_direct_rules(DATA / "direct_rules.json").customers), 4)
        self.assertEqual(len(load_indirect_rules(DATA / "indirect_rules.json").coverage), 3)

    def test_two_rules_for_one_trade_area_are_rejected(self):
        def mutate(data):
            data["coverage"].append(copy.deepcopy(data["coverage"][0]))
        self.check_rejected("direct_rules.json", mutate, load_direct_rules)

    def test_unknown_owner_is_rejected(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["coverage"][0].update(owner_id="missing"), load_direct_rules)

    def test_owner_cannot_be_their_own_deputy(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["coverage"][0].update(deputy_id="D-03"), load_direct_rules)

    def test_person_from_other_channel_is_rejected(self):
        self.check_rejected("indirect_rules.json",
                            lambda data: data["people"][0].update(channel="direkte"), load_indirect_rules)

    def test_customer_data_in_partner_file_is_rejected(self):
        self.check_rejected("indirect_rules.json", lambda data: data.update(customers=[]), load_indirect_rules)

    def test_false_string_is_not_treated_as_active(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["people"][0].update(active="false"), load_direct_rules)

    def test_private_flag_in_public_opportunity_is_rejected(self):
        self.check_rejected("opportunities.json",
                            lambda data: data["opportunities"][0].update(public_flags=["INSTALLERT_BASE"]), load_opportunities)

    def test_unmarked_input_is_rejected(self):
        self.check_rejected("opportunities.json", lambda data: data.update(synthetic=False), load_opportunities)

    def test_invalid_date_is_rejected(self):
        self.check_rejected("opportunities.json",
                            lambda data: data["opportunities"][0].update(deadline="2026-02-30"), load_opportunities)

    def test_duplicate_prepared_opportunity_id_is_rejected(self):
        def mutate(data):
            data["opportunities"].append(copy.deepcopy(data["opportunities"][0]))
        self.check_rejected("opportunities.json", mutate, load_opportunities)

    def test_duplicate_customer_org_number_is_rejected(self):
        def mutate(data):
            data["customers"].append(copy.deepcopy(data["customers"][0]))
        self.check_rejected("direct_rules.json", mutate, load_direct_rules)

    def test_invalid_person_trade_is_rejected(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["people"][0].update(trade_codes=["UNKNOWN"]), load_direct_rules)

    def test_duplicate_person_trade_is_rejected(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["people"][0].update(trade_codes=["BA", "BA"]), load_direct_rules)

    def test_invalid_capacity_is_rejected(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["people"][0].update(capacity=True), load_direct_rules)

    def test_prior_contact_must_be_a_known_direct_person(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["customers"][0].update(prior_contact_ids=["P-01"]), load_direct_rules)

    def test_duplicate_prior_contacts_are_rejected(self):
        self.check_rejected("direct_rules.json",
                            lambda data: data["customers"][0].update(prior_contact_ids=["D-01", "D-01"]), load_direct_rules)

    def test_missing_capacity_means_unknown_not_available(self):
        payload = json.loads((DATA / "direct_rules.json").read_text(encoding="utf-8"))
        payload["people"][0].pop("capacity")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "direct_rules.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rules = load_direct_rules(path)
        self.assertEqual(rules.people["D-01"].capacity, Capacity.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
