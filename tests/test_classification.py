"""Check classification decisions and boundaries, rather than model confidence."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mission_distribution.classification import (
    CpvRule, KeywordRule, classify, cpv_code, load_classification_cases,
    load_classification_rules, parse_classification_input,
)
from mission_distribution.models import DemoDataError


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demo_data"


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_classification_rules(DATA / "classification_rules.json")
        self.cases = load_classification_cases(DATA / "classification_examples.json")

    def test_eight_examples_have_explicit_expected_outcomes(self):
        expected = [
            ("relevant", "BA", "Vest", "service"),
            ("relevant", "BA", "Vest", "installasjon"),
            ("relevant", "SE", "Nord", "leveranse"),
            ("fag_ukjent", None, "Vest", "installasjon"),
            ("ikke_relevant", None, "Vest", "service"),
            ("ikke_relevant", None, "Øst", "ukjent"),
            ("relevant", "FS", "Øst", "ukjent"),
            ("relevant", "SE", None, "service"),
        ]
        for case, outcome in zip(self.cases, expected):
            with self.subTest(case=case.id):
                result = classify(case, self.rules)
                self.assertEqual(tuple(result[field] for field in ("relevance", "main_trade", "area", "work_type")), outcome)

    def test_most_specific_cpv_rule_wins_without_extra_broad_trade(self):
        rules = replace(self.rules, cpv_rules=(CpvRule("50", "FS"), CpvRule("50700000", "BA")))
        result = classify(replace(self.cases[0], title="Demo", description=None), rules)
        self.assertEqual(result["main_trade"], "BA")
        self.assertEqual(result["other_trades"], [])
        self.assertEqual(result["hits"][0]["matched_prefix"], "50700000")

    def test_main_cpv_overrides_priority_but_keeps_keyword_trades(self):
        result = classify(replace(self.cases[2], description="SD-anlegg og brannalarm"), self.rules)
        self.assertEqual(result["main_trade"], "SE")
        self.assertEqual(result["main_trade_basis"], "hoved_cpv")
        self.assertEqual(result["other_trades"], ["BA", "FS"])

    def test_additional_cpv_can_make_notice_relevant(self):
        value = replace(self.cases[5], additional_cpvs=("50610000",))
        result = classify(value, self.rules)
        self.assertEqual(result["main_trade"], "SE")
        self.assertEqual(result["hits"][0]["role"], "additional")

    def test_broad_cpv_keeps_unknown_trade_in_routing(self):
        result = classify(self.cases[3], self.rules)
        self.assertTrue(result["should_route"])
        self.assertIsNone(result["main_trade"])
        self.assertEqual(result["hits"], [])

    def test_keyword_resolves_broad_cpv(self):
        result = classify(replace(self.cases[3], description="Brannalarm"), self.rules)
        self.assertEqual(result["relevance"], "relevant")
        self.assertEqual(result["main_trade"], "FS")

    def test_excluded_cpv_does_not_exclude_other_relevant_work(self):
        result = classify(replace(self.cases[4], description="Heis og brannalarm"), self.rules)
        self.assertEqual(result["main_trade"], "FS")
        self.assertTrue(result["should_route"])
        self.assertEqual(result["excluded_codes"], ["50750000"])

    def test_keyword_case_punctuation_and_word_boundary(self):
        for text, expected in [("SD-ANLEGG", "BA"), ("SD anlegg", "BA"), ("(brannalarm)", "FS"),
                               ("xbrannalarmx", None)]:
            with self.subTest(text=text):
                value = replace(self.cases[5], title=text, description=None)
                self.assertEqual(classify(value, self.rules)["main_trade"], expected)

    def test_phrase_cannot_be_formed_across_title_and_description(self):
        rules = replace(self.rules, keyword_rules=(KeywordRule("teknisk alarm", "FS"),))
        value = replace(self.cases[5], title="Demo teknisk", description="alarm service")
        self.assertFalse(classify(value, rules)["should_route"])

    def test_brand_hit_does_not_establish_relevance(self):
        result = classify(replace(self.cases[5], description="Siemens"), self.rules)
        self.assertEqual(result["brand_hits"], ["Siemens"])
        self.assertFalse(result["should_route"])

    def test_phase_is_explicit_not_inferred_from_title(self):
        early = classify(self.cases[6], self.rules)
        ordinary = classify(replace(self.cases[6], notice_kind="competition"), self.rules)
        self.assertIn("TIDLIG_FASE", early["public_flags"])
        self.assertNotIn("TIDLIG_FASE", ordinary["public_flags"])

    def test_delivery_location_precedes_buyer_location(self):
        self.assertEqual(classify(self.cases[0], self.rules)["area"], "Vest")

    def test_buyer_fallback_only_when_delivery_is_missing(self):
        missing = replace(self.cases[0], delivery_municipalities=())
        unknown = replace(self.cases[0], delivery_municipalities=("9999",))
        self.assertEqual(classify(missing, self.rules)["area"], "Øst")
        self.assertIsNone(classify(unknown, self.rules)["area"])

    def test_multiple_delivery_areas_use_buyer_and_flag(self):
        result = classify(self.cases[1], self.rules)
        self.assertEqual(result["area"], "Vest")
        self.assertIn("FLERE_OMRÅDER", result["public_flags"])
        result = classify(replace(self.cases[1], buyer_municipality=None), self.rules)
        self.assertIsNone(result["area"])

    def test_partially_unknown_delivery_is_not_guessed(self):
        value = replace(self.cases[0], delivery_municipalities=("9901", "9999"))
        self.assertIsNone(classify(value, self.rules)["area"])

    def test_priority_is_configurable_when_main_cpv_has_no_trade(self):
        rules = replace(self.rules, trade_priority=("FS", "SE", "BA"))
        result = classify(self.cases[1], rules)
        self.assertEqual(result["main_trade"], "FS")
        self.assertEqual(set(result["other_trades"]), {"BA", "SE"})

    def test_cpv_format_normalizes_suffix_and_rejects_invalid_input(self):
        self.assertEqual(cpv_code("50700000-2"), "50700000")
        for code in ("5070000", "50700000-22", 50700000, "abcdefgh"):
            with self.subTest(code=code), self.assertRaises(DemoDataError):
                cpv_code(code)

    def test_invalid_kind_is_reported_as_input_error(self):
        for kind in ("award", [], None):
            with self.subTest(kind=kind), self.assertRaises(DemoDataError):
                parse_classification_input({"id": "x", "title": "Demo", "notice_kind": kind})

    def test_invalid_rule_tables_are_rejected(self):
        baseline = json.loads((DATA / "classification_rules.json").read_text())
        modifications = [
            {"cpv_rules": [{"prefix": "50", "trade": "BA"}, {"prefix": "50", "trade": "FS"}]},
            {"cpv_rules": [{"prefix": "x", "trade": "BA"}]},
            {"keyword_rules": [{"phrase": "SD-anlegg", "trade": "BA"}, {"phrase": "sd anlegg", "trade": "FS"}]},
            {"keyword_rules": [{"phrase": "---", "trade": "BA"}]},
            {"trade_priority": ["BA", "BA", "SE"]},
            {"brand_words": ["Siemens", "siemens"]},
            {"brand_words": ["---"]},
            {"type_prefixes": {"service": ["50"], "leveranse": ["50"]}},
            {"excluded_codes": ["45310000"]},
            {"synthetic": False},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            for change in modifications:
                with self.subTest(change=change):
                    path.write_text(json.dumps({**baseline, **change}))
                    with self.assertRaises(DemoDataError):
                        load_classification_rules(path)

    def test_cli_text_explains_hits_and_json_is_parseable(self):
        command = [sys.executable, "-m", "mission_distribution", "classify",
                   str(DATA / "classification_examples.json")]
        output = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertIn("CPV 50700000 → BA", output)
        self.assertIn("ukjent fag – går videre", output)
        self.assertIn("bortsortert etter demoreglene", output)
        parsed = json.loads(subprocess.run(command + ["--json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        self.assertFalse(parsed["ai_used"])
        self.assertEqual(len(parsed["assessments"]), 8)


if __name__ == "__main__":
    unittest.main()
