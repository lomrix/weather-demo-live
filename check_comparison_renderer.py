"""Focused checks for the offline Hamar comparison browser page."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RENDERER = ROOT / "harness" / "render_comparison.py"


def checked_result():
    journeys = [
        ("reachable", 100, 120, 130, 130),
        ("restored", 200, None, 220, None),
        ("unreachable", 300, None, None, 340),
    ]
    closure_only = []
    option_a = []
    option_b = []
    for journey_id, baseline, closure, option_a_metres, option_b_metres in journeys:
        closure_only.append({
            "journey_id": journey_id,
            "baseline": {"metres": baseline, "path": ["origin", journey_id]},
            "route": {"metres": closure, "path": [] if closure is None else ["origin", journey_id]},
        })
        option_a.append({
            "journey_id": journey_id,
            "baseline_metres": baseline,
            "closure_metres": closure,
            "candidate_metres": option_a_metres,
            "access_restored": closure is None and option_a_metres is not None,
            "unreachable_after_closure": closure is None,
            "unreachable_with_candidate": option_a_metres is None,
            "change_vs_baseline": None if option_a_metres is None else option_a_metres - baseline,
            "change_vs_closure": None if option_a_metres is None or closure is None else option_a_metres - closure,
        })
        option_b.append({
            "journey_id": journey_id,
            "baseline_metres": baseline,
            "closure_metres": closure,
            "candidate_metres": option_b_metres,
            "access_restored": closure is None and option_b_metres is not None,
            "unreachable_after_closure": closure is None,
            "unreachable_with_candidate": option_b_metres is None,
            "change_vs_baseline": None if option_b_metres is None else option_b_metres - baseline,
            "change_vs_closure": None if option_b_metres is None or closure is None else option_b_metres - closure,
        })
    return {
        "kind": "comparison_draft",
        "proposal": {"rationale": "Unchecked synthetic draft.", "options": []},
        "comparison": {
            "scenario": {
                "id": "test-case",
                "label": "Deterministic test case",
                "synthetic": True,
                "offline": True,
                "map_extract": {
                    "route_map": {
                        "node_coordinates": {
                            "origin": [60.0, 11.0],
                            "reachable": [60.001, 11.001],
                            "restored": [60.002, 11.002],
                            "unreachable": [60.003, 11.003],
                        },
                        "context_links": [],
                        "candidate_links": [],
                        "attribution": "OpenStreetMap contributors",
                    }
                },
            },
            "baseline": [
                {"journey_id": journey_id, "route": {"metres": baseline, "path": ["origin", journey_id]}}
                for journey_id, baseline, _, _, _ in journeys
            ],
            "alternatives": [
                {
                    "id": alternative_id,
                    "label": alternative_id,
                    "journeys": [
                        {
                            "journey_id": journey_id,
                            "route": {"metres": baseline, "path": ["origin", journey_id]},
                        }
                        for journey_id, baseline, _, _, _ in journeys
                    ],
                }
                for alternative_id in ("closure-only", "option-a", "option-b")
            ],
        },
        "impact_summary": {
            "closure_only": closure_only,
            "selected_candidates": [
                {"candidate_id": "option-a", "assumed_metres": 50, "assumption": "Test assumption.", "journeys": option_a},
                {"candidate_id": "option-b", "assumed_metres": 75, "assumption": "Test assumption.", "journeys": list(reversed(option_b))},
            ],
        },
    }


class ComparisonRendererTests(unittest.TestCase):
    def run_renderer(self, payload, output):
        return subprocess.run(
            [sys.executable, str(RENDERER), "--output", str(output)],
            input=json.dumps(payload),
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_checked_statuses_use_matched_journey_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.html"
            result = self.run_renderer(checked_result(), output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
        self.assertIn("Still reachable.", page)
        self.assertIn("Access restored.", page)
        self.assertIn("Still unreachable.", page)
        self.assertIn("Access lost.", page)
        self.assertIn("option-a", page)
        self.assertIn("option-b", page)

    def test_map_selects_each_journey_and_marks_current_journey(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.html"
            result = self.run_renderer(checked_result(), output)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
        self.assertIn('id="journey-selector"', page)
        self.assertIn('<option value="reachable">reachable</option>', page)
        self.assertIn('<option value="restored">restored</option>', page)
        self.assertIn('<option value="unreachable">unreachable</option>', page)
        self.assertIn('id="journey-map-status">Showing journey: reachable', page)
        self.assertIn('data-journey="restored"', page)
        self.assertIn('selector.addEventListener("change",refresh)', page)

    def test_clarification_has_no_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.html"
            result = self.run_renderer(
                {"kind": "clarifying_question", "question": "Does the closure affect pedestrians?"},
                output,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            page = output.read_text(encoding="utf-8")
        self.assertIn("Clarification needed", page)
        self.assertIn("No route comparison was calculated.", page)
        self.assertNotIn("Closure only", page)

    def test_mismatched_journey_ids_preserve_existing_report(self):
        payload = checked_result()
        payload["impact_summary"]["selected_candidates"][0]["journeys"][0]["journey_id"] = "unexpected"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.html"
            output.write_text("existing report", encoding="utf-8")
            result = self.run_renderer(payload, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing report")

    def test_duplicate_journey_ids_stop(self):
        payload = checked_result()
        payload["impact_summary"]["closure_only"][1]["journey_id"] = "reachable"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.html"
            result = self.run_renderer(payload, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate journey ID", result.stderr)

    def test_valid_input_creates_missing_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing" / "comparison.html"
            result = self.run_renderer(checked_result(), output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.is_file())

    def test_malformed_input_preserves_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison.html"
            output.write_text("existing report", encoding="utf-8")
            result = self.run_renderer({"comparison": {}}, output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing report")


if __name__ == "__main__":
    unittest.main()
