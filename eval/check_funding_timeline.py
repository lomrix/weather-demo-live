"""Synthetic answer-state tests using a saved real rule;
these do not verify timeline contents or funding eligibility."""

from pathlib import Path
import unittest

from harness.funding_timeline import check_timeline


RULE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "funding-timeline-rule.json"
SOURCE_URL = (
    "https://innlandetfylke.no/tjenester/sok-tilskudd/kunst-og-kultur/"
    "regionalt-kulturfond-innlandet.62589.aspx"
)


class FundingTimelineTests(unittest.TestCase):
    def test_false_is_missing(self):
        result = check_timeline(False, RULE_PATH)
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["source_url"], SOURCE_URL)

    def test_true_is_declared_present(self):
        result = check_timeline(True, RULE_PATH)
        self.assertEqual(result["status"], "declared_present")
        self.assertEqual(result["source_url"], SOURCE_URL)

    def test_none_is_unknown(self):
        result = check_timeline(None, RULE_PATH)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["source_url"], SOURCE_URL)

    def test_invalid_answer_is_rejected(self):
        with self.assertRaises(ValueError):
            check_timeline("yes", RULE_PATH)


if __name__ == "__main__":
    unittest.main()
