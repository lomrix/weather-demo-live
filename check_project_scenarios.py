"""Focused synthetic checks for date-bounded multi-project scenarios."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness.project_scenario import assess_projects
from harness.scenario_compare import compare_scenario


ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "fixtures" / "scenarios" / "synthetic-projects.json"
SINGLE = ROOT / "fixtures" / "scenarios" / "synthetic-access.json"
A, B = "station-road-works", "mill-lane-works"


def rows(result):
    journeys = result["comparison"]["alternatives"][0]["journeys"]
    return {row["journey_id"]: row for row in journeys}


class ProjectScenarioTests(unittest.TestCase):
    def setUp(self):
        self.scenario = json.loads(PROJECTS.read_text(encoding="utf-8"))

    def test_before_all_projects_nothing_changes(self):
        result = assess_projects(self.scenario, "2026-11-09")
        self.assertEqual(result["project_assessment"]["active_projects"], [])
        for row in rows(result).values():
            self.assertEqual(row["change_metres"], 0)
            self.assertEqual(row["contributing_projects"], [])

    def test_each_project_alone_leaves_usable_detours(self):
        only_a = rows(assess_projects(self.scenario, "2026-11-12"))
        self.assertEqual(only_a["home-to-school"]["route"]["metres"], 220)
        self.assertEqual(only_a["home-to-hall"]["route"]["metres"], 220)
        self.assertEqual(only_a["home-to-clinic"]["change_metres"], 0)
        self.assertEqual(only_a["north-to-school"]["change_metres"], 0)
        only_b = rows(assess_projects(self.scenario, "2026-11-23"))
        self.assertEqual(only_b["north-to-school"]["route"]["metres"], 290)
        self.assertEqual(only_b["north-to-school"]["contributing_projects"], [B])
        self.assertEqual(only_b["home-to-school"]["change_metres"], 0)
        for row in list(only_a.values()) + list(only_b.values()):
            self.assertIsNotNone(row["route"]["metres"])
            self.assertFalse(row["overlap_effect"])

    def test_overlap_lengthens_or_blocks_and_names_projects(self):
        result = assess_projects(self.scenario, "2026-11-18")
        active = [p["id"] for p in result["project_assessment"]["active_projects"]]
        self.assertEqual(active, [A, B])
        found = rows(result)
        self.assertEqual(found["home-to-school"]["route"]["metres"], 250)
        self.assertEqual(found["home-to-school"]["contributing_projects"], [A, B])
        self.assertIsNone(found["home-to-hall"]["route"]["metres"])
        self.assertEqual(found["home-to-hall"]["status"], "unreachable")
        self.assertEqual(found["north-to-school"]["route"]["metres"], 340)
        self.assertEqual(found["home-to-clinic"]["contributing_projects"], [])
        self.assertTrue(found["home-to-hall"]["overlap_effect"])
        self.assertFalse(found["home-to-clinic"]["overlap_effect"])

    def test_date_boundaries_are_inclusive(self):
        def active(day):
            result = assess_projects(self.scenario, day)
            return [p["id"] for p in result["project_assessment"]["active_projects"]]

        self.assertEqual(active("2026-11-09"), [])
        self.assertEqual(active("2026-11-10"), [A])
        self.assertEqual(active("2026-11-15"), [A])
        self.assertEqual(active("2026-11-16"), [A, B])
        self.assertEqual(active("2026-11-20"), [A, B])
        self.assertEqual(active("2026-11-21"), [B])
        self.assertEqual(active("2026-11-27"), [B])
        self.assertEqual(active("2026-11-28"), [])

    def test_one_day_project_is_active_on_that_day(self):
        self.scenario["projects"][0]["start_date"] = "2026-11-10"
        self.scenario["projects"][0]["end_date"] = "2026-11-10"
        result = assess_projects(self.scenario, "2026-11-10")
        self.assertEqual(result["project_assessment"]["active_projects"][0]["id"], A)

    def test_invalid_inputs_stop_clearly(self):
        def broken(change, message, day="2026-11-18"):
            scenario = copy.deepcopy(self.scenario)
            change(scenario)
            with self.assertRaisesRegex(ValueError, message):
                assess_projects(scenario, day)

        broken(lambda s: s["projects"][0].update(end_date="2026-11-09"), "before start_date")
        broken(lambda s: s["projects"][0].update(start_date="2026-02-30"), "not a real calendar date")
        broken(lambda s: s["projects"][0].update(start_date="10/11/2026"), "YYYY-MM-DD")
        broken(lambda s: s["projects"][0].pop("end_date"), "end_date must be a date")
        broken(lambda s: s["projects"][0]["restrictions"][0]["link_ids"].append("missing"),
               "project station-road-works: unknown link ID missing")
        broken(lambda s: s["projects"][0]["restrictions"][0]["link_ids"].append("centre-school"),
               "ambiguous repeated link")
        broken(lambda s: s["projects"][0].update(restrictions=[]), "restrictions are required")
        broken(lambda s: s["projects"][1].update(id=A), "project IDs must be unique")
        broken(lambda s: s["projects"][0]["restrictions"][0].update(mode="vehicle"),
               "requires walking mode")
        broken(lambda s: s.pop("projects"), "non-empty projects list")
        for bad in ("2026-13-01", "tomorrow", None):
            with self.subTest(date=bad), self.assertRaisesRegex(ValueError, "assessment date"):
                assess_projects(self.scenario, bad)

    def test_hypothetical_status_is_validated_and_carried_into_assessment(self):
        for day, expected in (("2026-11-09", False), ("2026-11-12", True), ("2026-11-18", True)):
            result = assess_projects(self.scenario, day)
            self.assertIs(result["project_assessment"]["hypothetical"], expected)
            self.assertIs(result["comparison"]["alternatives"][0]["hypothetical"], expected)
        mixed = copy.deepcopy(self.scenario)
        mixed["projects"][0]["hypothetical"] = False
        self.assertIs(assess_projects(mixed, "2026-11-12")["project_assessment"]["hypothetical"], False)
        self.assertIs(assess_projects(mixed, "2026-11-18")["project_assessment"]["hypothetical"], True)
        self.assertIs(assess_projects(mixed, "2026-11-23")["project_assessment"]["hypothetical"], True)
        mixed["projects"][1]["hypothetical"] = False
        self.assertIs(assess_projects(mixed, "2026-11-18")["project_assessment"]["hypothetical"], False)
        described = assess_projects(self.scenario, "2026-11-18")["project_assessment"]["active_projects"]
        self.assertTrue(all(project["hypothetical"] is True for project in described))
        for bad in (None, "true", 1, "missing"):
            scenario = copy.deepcopy(self.scenario)
            if bad == "missing":
                del scenario["projects"][0]["hypothetical"]
            else:
                scenario["projects"][0]["hypothetical"] = bad
            with self.subTest(value=bad), self.assertRaisesRegex(
                ValueError, "project station-road-works: hypothetical must be true or false"
            ):
                assess_projects(scenario, "2026-11-18")

    def test_single_closure_scenarios_still_work(self):
        single = json.loads(SINGLE.read_text(encoding="utf-8"))
        baseline = compare_scenario(single)
        single["projects"] = copy.deepcopy(self.scenario["projects"])
        self.assertEqual(compare_scenario(single)["alternatives"], baseline["alternatives"])
        with self.assertRaisesRegex(ValueError, "non-empty projects list"):
            assess_projects(json.loads(SINGLE.read_text(encoding="utf-8")), "2026-11-18")

    def test_cli_result_renders_in_existing_offline_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "projects.html"
            assessed = subprocess.run(
                [sys.executable, "harness/project_scenario.py", "--scenario", str(PROJECTS),
                 "--date", "2026-11-18", "--json"],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(assessed.returncode, 0, assessed.stderr)
            rendered = subprocess.run(
                [sys.executable, "harness/render_comparison.py", "--output", str(output)],
                cwd=ROOT, input=assessed.stdout, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            page = output.read_text(encoding="utf-8")
        for expected in (
            "Active projects", "Assessment date:</strong> 2026-11-18", "inclusive",
            "Station Road works (synthetic)", "Mill Lane works (synthetic)",
            "No route available", "250 m", "station-road-works, mill-lane-works",
            "Hypothetical assessment", "hypothetical)",
        ):
            self.assertIn(expected, page)

    def test_invalid_cli_date_range_exits_with_message(self):
        with tempfile.TemporaryDirectory() as folder:
            scenario = copy.deepcopy(self.scenario)
            scenario["projects"][0]["end_date"] = "2026-01-01"
            path = Path(folder) / "bad.json"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "harness/project_scenario.py", "--scenario", str(path),
                 "--date", "2026-11-18"],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("before start_date", result.stderr)


if __name__ == "__main__":
    unittest.main()
