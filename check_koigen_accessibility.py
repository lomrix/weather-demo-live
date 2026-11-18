"""Focused checks for Koigen accessibility evidence and route gaps."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))

from workspace_service import Workspace


def request():
    return {
        "case_id": "koigen-demo",
        "assessment_date": "2026-10-27",
        "modeled_section_confirmation": True,
        "projects": [{
            "name": "Modeled Koigen candidate closure",
            "start_date": "2026-10-27",
            "end_date": "2026-10-27",
            "sections": ["koigen-candidate-closure"],
            "hypothetical": True,
        }],
    }


class KoigenAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = Workspace(ROOT)
        cls.result = cls.workspace.assess(request())
        cls.accessibility = cls.result["accessibility"]

    def test_route_evidence_preserves_distances_and_provenance(self):
        summary = self.accessibility
        self.assertEqual(
            (summary["shortest_route_metres"], summary["modeled_detour_metres"]),
            (323, 593),
        )
        self.assertEqual(summary["baseline"]["metres"], 323)
        self.assertEqual(summary["modeled_detour"]["metres"], 593)
        self.assertEqual(summary["provenance"]["route_nodes_checked"], 66)
        self.assertIn("OpenStreetMap contributors", summary["provenance"]["attribution"])
        self.assertTrue(summary["provenance"]["evidence_checked_at"])

    def test_absent_step_tags_remain_unknown_for_both_routes(self):
        baseline = self.accessibility["baseline"]["step_status_metres"]
        detour = self.accessibility["modeled_detour"]["step_status_metres"]
        self.assertEqual(baseline, {
            "known_steps": 0,
            "supported_step_free": 0,
            "unknown": 323,
        })
        self.assertEqual(detour, {
            "known_steps": 0,
            "supported_step_free": 0,
            "unknown": 593,
        })
        self.assertEqual(
            self.accessibility["alternative"]["status"],
            "not_supported_by_evidence",
        )
        self.assertIsNone(self.accessibility["alternative"]["metres"])
        self.assertIn(
            f"{baseline['unknown']} m of baseline links",
            self.accessibility["alternative"]["reason"],
        )
        self.assertIn(
            f"{detour['unknown']} m of modeled-detour links",
            self.accessibility["alternative"]["reason"],
        )

    def test_surface_is_sourced_and_slope_is_not_inferred(self):
        self.assertEqual(
            self.accessibility["baseline"]["surface_metres"],
            {"fine_gravel": 323},
        )
        self.assertEqual(
            self.accessibility["modeled_detour"]["surface_metres"],
            {"fine_gravel": 125, "pebblestone": 116, "unknown": 272, "unpaved": 80},
        )
        self.assertEqual(
            self.accessibility["baseline"]["slope_metres"],
            {"unknown": 323},
        )
        self.assertEqual(
            self.accessibility["modeled_detour"]["slope_metres"],
            {"unknown": 593},
        )
        self.assertTrue(all(
            link["slope"] == "unknown"
            for link in self.accessibility["baseline"]["links"]
            + self.accessibility["modeled_detour"]["links"]
        ))

    def test_accessibility_summary_is_available_even_when_closure_is_inactive(self):
        payload = request()
        payload["assessment_date"] = "2026-10-26"
        result = self.workspace.assess(payload)
        self.assertEqual(result["journeys"][0]["metres"], 323)
        self.assertEqual(result["accessibility"]["modeled_detour_metres"], 593)

    def test_client_shows_requirement_and_never_equates_absence_with_step_free(self):
        script = (ROOT / "workspace" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "workspace" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Accessibility requirement: avoid steps", html)
        self.assertIn("An absent steps tag is unknown, not step-free", script)
        self.assertIn("Two-dimensional coordinates were not used to infer slope", script)


if __name__ == "__main__":
    unittest.main()
