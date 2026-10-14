"""Synthetic error-case tests for the offline probe, not live experiments."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.probe import write_probe


class ProbeInputTests(unittest.TestCase):
    """Check invalid synthetic inputs leave no output directories or files."""

    def test_missing_input(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "missing.json"
            output_path = root / "not-created" / "probe.json"

            with self.assertRaises(FileNotFoundError):
                write_probe(input_path, output_path)

            self.assertFalse(output_path.exists())
            self.assertFalse(output_path.parent.exists())

    def test_invalid_json(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "invalid.json"
            output_path = root / "not-created" / "probe.json"
            input_path.write_text("{invalid JSON", encoding="utf-8")

            with self.assertRaises(json.JSONDecodeError):
                write_probe(input_path, output_path)

            self.assertFalse(output_path.exists())
            self.assertFalse(output_path.parent.exists())

    def test_missing_source_quote(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "missing-quote.json"
            output_path = root / "not-created" / "probe.json"
            fixture_path = ROOT / "fixtures" / "funding-timeline-rule.json"
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            del fixture["source_quote"]
            input_path.write_text(
                json.dumps(fixture, ensure_ascii=False), encoding="utf-8"
            )

            with self.assertRaises(ValueError):
                write_probe(input_path, output_path)

            self.assertFalse(output_path.exists())
            self.assertFalse(output_path.parent.exists())


if __name__ == "__main__":
    unittest.main()
