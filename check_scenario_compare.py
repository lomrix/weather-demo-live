"""Focused checks for the offline scenario comparison engine."""

import copy
import json
import unittest
from pathlib import Path

from harness.scenario_compare import compare_scenario


ROOT = Path(__file__).resolve().parent
SCENARIO = ROOT / "fixtures" / "scenarios" / "synthetic-access.json"
SECOND_SCENARIO = ROOT / "fixtures" / "scenarios" / "synthetic-park.json"


class ScenarioComparisonTests(unittest.TestCase):
    def setUp(self):
        self.scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))

    def test_synthetic_scenario_reports_restoration_and_vehicle_restriction(self):
        result = compare_scenario(self.scenario)
        self.assertTrue(result["scenario"]["synthetic"])
        temporary = result["alternatives"][0]["journeys"][0]
        self.assertEqual(temporary["route"]["metres"], 190)
        self.assertEqual(temporary["change_metres"], -10)
        vehicle = result["alternatives"][1]["journeys"][0]
        self.assertEqual(vehicle["route"]["metres"], 200)
        self.assertEqual(vehicle["change_metres"], 0)

    def test_unknown_link_id_stops(self):
        scenario = copy.deepcopy(self.scenario)
        scenario["alternatives"][0]["operations"][0]["link_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown link ID"):
            compare_scenario(scenario)

    def test_ambiguous_operation_stops(self):
        scenario = copy.deepcopy(self.scenario)
        scenario["alternatives"][0]["operations"][0]["link_ids"].append(
            "home-to-crossing"
        )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            compare_scenario(scenario)

    def test_non_walking_close_does_not_remove_walking_link(self):
        scenario = copy.deepcopy(self.scenario)
        scenario["alternatives"][0]["operations"] = [
            {"type": "close_links", "mode": "vehicle", "link_ids": ["home-to-crossing"]}
        ]
        with self.assertRaisesRegex(ValueError, "requires walking mode"):
            compare_scenario(scenario)

    def test_added_link_reuses_link_validation(self):
        invalid_links = (
            ({"modes": [""]}, "modes must be a non-empty list"),
            ({"id": " "}, "link IDs must be unique, non-empty strings"),
            ({"from": "Unknown"}, "invalid hypothetical walking link"),
        )
        for change, message in invalid_links:
            scenario = copy.deepcopy(self.scenario)
            scenario["alternatives"][0]["operations"][1]["links"][0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                compare_scenario(scenario)

    def test_added_link_requires_explicit_hypothetical_true(self):
        for value in (None, False, "true"):
            scenario = copy.deepcopy(self.scenario)
            if value is None:
                del scenario["alternatives"][0]["hypothetical"]
            else:
                scenario["alternatives"][0]["hypothetical"] = value
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "requires hypothetical true"
            ):
                compare_scenario(scenario)

    def test_different_scenario_file_loads_without_code_changes(self):
        scenario = json.loads(SECOND_SCENARIO.read_text(encoding="utf-8"))
        result = compare_scenario(scenario)
        self.assertEqual(result["scenario"]["id"], "synthetic-park")
        self.assertEqual(result["baseline"][0]["route"]["metres"], 200)


if __name__ == "__main__":
    unittest.main()
