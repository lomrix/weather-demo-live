"""Focused offline checks for the Ringgata replay and browser output."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "ringgata_demo.py"
CASE = ROOT / "fixtures" / "ringgata-demo" / "ringgata.json"
BUS = ROOT / "fixtures" / "hamar-route-coverage-2026-10-21.json"


class RinggataReplayTests(unittest.TestCase):
    def run_demo(self, *args):
        return subprocess.run(
            [sys.executable, str(DEMO), *map(str, args)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_normal_replay_has_required_values(self):
        result = self.run_demo("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["comparison"]["baseline"]["metres"], 800)
        self.assertEqual(data["comparison"]["crossing_closed"]["metres"], 1050)
        self.assertEqual(data["comparison"]["extra_metres"], 250)
        self.assertEqual(data["transport_context"]["totals"], {
            "journeys": 10, "calls": 26, "actual": 13, "prediction_only": 13,
            "unknown": 0, "cancelled": 0,
        })

    def test_wrong_notice_location_stops(self):
        case = json.loads(CASE.read_text(encoding="utf-8"))
        case["notice_location"] = "Wrong location"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            result = self.run_demo("--case", path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr)

    def test_missing_bus_input_stops_without_success_page(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_bus = Path(directory) / "missing.json"
            output = Path(directory) / "ringgata.html"
            output.write_text("existing page", encoding="utf-8")
            result = self.run_demo("--bus", missing_bus)
            self.assertEqual(result.stdout, "")
            render = subprocess.run(
                [
                    sys.executable, str(ROOT / "harness" / "render_ringgata.py"),
                    "--output", str(output),
                ],
                input=result.stdout,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(render.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing page")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Demo stopped:", result.stderr)

    def test_valid_render_creates_missing_parent(self):
        result = self.run_demo("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing" / "ringgata.html"
            render = subprocess.run(
                [
                    sys.executable, str(ROOT / "harness" / "render_ringgata.py"),
                    "--output", str(output),
                ],
                input=result.stdout,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(render.returncode, 0, render.stderr)
            self.assertTrue(output.is_file())

    def test_empty_render_does_not_create_missing_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing" / "ringgata.html"
            render = subprocess.run(
                [
                    sys.executable, str(ROOT / "harness" / "render_ringgata.py"),
                    "--output", str(output),
                ],
                input="",
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(render.returncode, 0)
            self.assertFalse(output.parent.exists())
            self.assertFalse(output.exists())

    def test_closed_crossing_disconnects_valid_baseline(self):
        case = json.loads(CASE.read_text(encoding="utf-8"))
        case["edges"] = [
            edge for edge in case["edges"]
            if edge["id"] in {"direct-approach", "direct-crossing"}
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "disconnected.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            result = self.run_demo("--case", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(self.run_demo("--case", path, "--json").stdout)
            self.assertEqual(data["comparison"]["baseline"]["metres"], 800)
            self.assertIsNone(data["comparison"]["crossing_closed"]["metres"])
            render = subprocess.run(
                [
                    sys.executable, str(ROOT / "harness" / "render_ringgata.py"),
                    "--output", str(Path(directory) / "disconnected.html"),
                ],
                input=self.run_demo("--case", path, "--json").stdout,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(render.returncode, 0, render.stderr)
            page = (Path(directory) / "disconnected.html").read_text(encoding="utf-8")
            self.assertIn("No route available", page)

    def test_disconnected_baseline_stops(self):
        case = json.loads(CASE.read_text(encoding="utf-8"))
        case["edges"] = [
            {"id": "partial", "from": "Start", "to": "Direct crossing", "metres": 500},
            {"id": "isolated", "from": "Demo bus stop", "to": "Isolated", "metres": 100},
        ]
        case["closure_edge"] = "partial"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "disconnected-baseline.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            result = self.run_demo("--case", path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline journey has no route", result.stderr)

    def test_rendered_page_contains_required_labels(self):
        result = self.run_demo("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ringgata.html"
            render = subprocess.run(
                [
                    sys.executable, str(ROOT / "harness" / "render_ringgata.py"),
                    "--output", str(output),
                ],
                input=result.stdout,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(render.returncode, 0, render.stderr)
            page = output.read_text(encoding="utf-8")
        self.assertEqual(render.returncode, 0, render.stderr)
        self.assertIn("800 m", page)
        self.assertIn("1,050 m", page)
        self.assertIn("+250 m", page)
        self.assertIn("hypothetical", page)
        self.assertIn("illustrative", page)
        self.assertIn("26 stop calls", page)
        self.assertIn("13 actual", page)
        self.assertIn("13 prediction-only", page)
        self.assertIn("unverified", page)


if __name__ == "__main__":
    unittest.main()
