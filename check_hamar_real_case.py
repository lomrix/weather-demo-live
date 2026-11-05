"""Checks for the bounded Hamar real-data scenario."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.scenario_compare import compare_scenario
from harness.import_hamar_osm import _is_walking_way, import_scenario
from harness.ollama_scenario import run_comparison


ROOT = Path(__file__).resolve().parent
SCENARIO = ROOT / "fixtures" / "scenarios" / "hamar-ringgata-ankerskogen.json"
SECOND_SCENARIO = ROOT / "fixtures" / "scenarios" / "hamar-furubergvegen-masabekkvegen.json"
MAP_INPUT_DIR = Path(
    os.environ.get("HAMAR_OSM_INPUT_DIR", ROOT / "fixtures" / "maps")
)
RINGGATA_MAP = MAP_INPUT_DIR / "ringgata.osm"
FURUBERGVEGEN_MAP = MAP_INPUT_DIR / "furubergvegen-masabekkvegen.osm"


class HamarRealCaseTests(unittest.TestCase):
    def setUp(self):
        self.scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))

    def test_mapped_route_and_alternatives(self):
        result = compare_scenario(self.scenario)
        self.assertFalse(result["scenario"]["synthetic"])
        self.assertEqual(result["baseline"][0]["route"]["metres"], 1384)
        self.assertEqual(result["alternatives"][0]["journeys"][0]["route"]["metres"], 1384)
        self.assertIsNone(result["alternatives"][1]["journeys"][0]["route"]["metres"])

    def test_school_entrance_gap_is_documented(self):
        self.assertIn("2284553352", " ".join(self.scenario["metadata"]["unknowns"]))
        self.assertEqual(self.scenario["metadata"]["secondary_plan"]["id"], "080400")
        evidence = self.scenario["metadata"]["map_extract"]
        self.assertEqual(evidence["origin"]["node_id"], "3223998135")
        self.assertEqual(evidence["interrupted_link"]["way_id"], "1396077789")
        self.assertEqual(
            evidence["alternative_finding"],
            "No alternative found in the saved walking network",
        )
        self.assertEqual(evidence["interrupted_link"]["coordinates"]["from"], [60.7987973, 11.0880717])
        self.assertEqual(evidence["interrupted_link"]["coordinates"]["to"], [60.7999568, 11.0861151])
        self.assertEqual(evidence["interrupted_link"]["section_metres_geometry"], 169.4)

    def test_downloaded_map_import_preserves_way_and_finds_detour(self):
        source = RINGGATA_MAP
        if not source.is_file():
            self.skipTest("approved local map input is unavailable")
        imported = import_scenario(source, SCENARIO)
        result = compare_scenario(imported)
        self.assertEqual(result["baseline"][0]["route"]["metres"], 1384)
        interrupted = result["alternatives"][1]["journeys"][0]["route"]
        self.assertEqual(interrupted["metres"], 2332)
        self.assertEqual(interrupted["metres"] - 1384, 948)
        self.assertEqual(
            imported["metadata"]["map_extract"]["interrupted_link"]["closure_segment_ids"],
            [f"osm-way-1396077789-segment-{i}" for i in range(7, 14)],
        )
        extract = imported["metadata"]["map_extract"]
        self.assertNotIn("alternative_finding", extract)
        self.assertNotIn("downloaded_baseline_metres", extract)
        self.assertNotIn("downloaded_detour_metres", extract)
        self.assertNotIn("downloaded_detour_change_metres", extract)
        page = self._render_page(imported)
        self.assertIn("Detour found in checked walking comparison", page)
        self.assertIn("Mapped route map", page)
        self.assertIn("data-layer=\"baseline\"", page)
        self.assertIn("data-layer=\"detour\"", page)
        self.assertIn("data-layer=\"interruption\"", page)
        self.assertIn("© OpenStreetMap contributors", page)
        self.assertIn(">Start<", page)
        self.assertIn(">Destination<", page)

    def test_explicit_foot_no_overrides_walking_defaults(self):
        self.assertFalse(_is_walking_way({"highway": "footway", "foot": "no"}))
        self.assertFalse(_is_walking_way({"highway": "cycleway", "foot": "no"}))
        self.assertTrue(_is_walking_way({"highway": "footway"}))
        self.assertTrue(_is_walking_way({"highway": "service", "foot": "designated"}))

    def test_ollama_candidates_keep_confirmed_closure_and_map_checked_routes(self):
        source = RINGGATA_MAP
        if not source.is_file():
            self.skipTest("approved local map input is unavailable")
        imported = import_scenario(source, SCENARIO)
        closure_links = imported["metadata"]["map_extract"]["interrupted_link"]["closure_segment_ids"]
        proposal = {
            "kind": "comparison_draft",
            "rationale": "Compare the three mapped connector options.",
            "options": [
                {"candidate_id": "junction-west-connector", "reason": "Shortest checked mitigation."},
                {"candidate_id": "central-path-connector", "reason": "Longer central option."},
            ],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            result = run_comparison(
                imported,
                "Compare two pedestrian mitigations.",
                "walking",
                closure_links,
            )
        self.assertEqual(result["comparison"]["baseline"][0]["route"]["metres"], 1384)
        self.assertEqual(
            result["comparison"]["alternatives"][0]["journeys"][0]["route"]["metres"],
            2332,
        )
        for alternative in result["comparison"]["alternatives"][1:]:
            self.assertEqual(alternative["closure_link_ids"], closure_links)
        page = self._render_result(result)
        for alternative in result["comparison"]["alternatives"]:
            route = alternative["journeys"][0]["route"]
            self.assertIn(
                f'data-route-path="{",".join(route["path"])}"',
                page,
            )
        self.assertIn("Site check:", page)
        self.assertIn("Selected proposed links", page)
        self.assertIn("Saved vs closure only (2,332 m): 855 m.", page)
        self.assertIn("Saved vs closure only (2,332 m): 355 m.", page)
        self.assertIn("Added vs baseline (1,384 m): 93 m.", page)
        self.assertIn("Added vs baseline (1,384 m): 593 m.", page)
        self.assertIn("<details class=\"draft diagnostics\">", page)
        visible_report = page.split("<details", 1)[0]
        self.assertNotIn("93%", visible_report)
        self.assertNotIn("59.3%", visible_report)
        self.assertIn(".route-option-1 {", page)
        self.assertIn(".route-option-2 {", page)
        self.assertIn("route-option-1-key", page)
        self.assertIn("route-option-2-key", page)

    def test_real_case_renders_with_evidence_gaps(self):
        page = self._render_page(self.scenario)
        self.assertIn("Real-data case", page)
        self.assertIn("Ankerskogen", page)
        self.assertIn("2284553352", page)
        self.assertIn("No alternative found in the saved walking network", page)
        self.assertIn("modeled scenario", page)

    def test_second_real_case_uses_same_import_compare_and_selection_workflow(self):
        source = FURUBERGVEGEN_MAP
        if not source.is_file():
            self.skipTest("approved Furubergvegen map input is unavailable")
        scenario = import_scenario(source, SECOND_SCENARIO)
        comparison = compare_scenario(scenario)
        self.assertEqual(
            [row["route"]["metres"] for row in comparison["baseline"]],
            [201, 241],
        )
        closure_links = scenario["metadata"]["map_extract"]["interrupted_link"]["closure_segment_ids"]
        proposal = {
            "kind": "comparison_draft",
            "rationale": "Compare the two checked junction options.",
            "options": [
                {"candidate_id": "east-side-path-connector", "reason": "Keeps both journeys available."},
                {"candidate_id": "north-campus-connector", "reason": "Shorter checked north connection."},
            ],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            checked = run_comparison(
                scenario,
                "Compare two hypothetical pedestrian mitigations.",
                "walking",
                closure_links,
            )
        self.assertEqual(
            [row["route"]["metres"] for row in checked["comparison"]["alternatives"][0]["journeys"]],
            [362, 402],
        )
        self.assertEqual(
            [row["route"]["metres"] for row in checked["comparison"]["alternatives"][2]["journeys"]],
            [268, 292],
        )
        for option in checked["comparison"]["alternatives"][1:]:
            self.assertEqual(option["closure_link_ids"], closure_links)
        page = self._render_result(checked)
        self.assertIn("Furubergvegen", page)
        self.assertIn("junction-to-north-path", page)
        self.assertIn("junction-to-further-path", page)
        self.assertIn("Raw Ollama diagnostics", page)
        self.assertIn("Added vs baseline (201 m): 161 m.", page)
        self.assertIn("Saved vs closure only (362 m): 0 m.", page)
        self.assertIn("Added vs baseline (241 m): 161 m.", page)
        self.assertIn("Saved vs closure only (402 m): 0 m.", page)

    def _render_page(self, scenario):
        checked = {"comparison": compare_scenario(scenario)}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "hamar.html"
            rendered = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "harness" / "render_comparison.py"),
                    "--output",
                    str(output),
                ],
                input=json.dumps(checked),
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            return output.read_text(encoding="utf-8")

    def _render_result(self, result):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "hamar.html"
            rendered = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "harness" / "render_comparison.py"),
                    "--output",
                    str(output),
                ],
                input=json.dumps(result),
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            return output.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
