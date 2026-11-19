"""Focused checks for the saved Koigen notice-to-map workflow."""

import json
import sys
import unittest
from pathlib import Path
from urllib.error import URLError


ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))

from notice_draft import load_notice, review_draft
from workspace_service import Workspace
from check_notice_evidence import koigen_reply


class FakeResponse:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.raw


class FakeOpener:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = 0

    def __call__(self, _request, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return FakeResponse(json.dumps({"response": json.dumps(self.reply)}).encode("utf-8"))


def koigen_request(confirmation=False):
    return {
        "case_id": "koigen-demo",
        "assessment_date": "2026-10-27",
        "modeled_section_confirmation": confirmation,
        "projects": [{
            "name": "Modeled Koigen candidate closure",
            "start_date": "2026-10-27",
            "end_date": "2026-10-27",
            "sections": ["koigen-candidate-closure"],
            "hypothetical": True,
        }],
    }


class KoigenNoticeTests(unittest.TestCase):
    def setUp(self):
        self.notice = load_notice(ROOT)
        self.reference = self.notice["hand_reference"]

    def test_unsupported_evidence_is_replaced_by_checked_reference(self):
        focus = self.notice["focus_sentence_id"]
        draft = {
            "location": "pumpestasjon",
            "travel_modes": ["walking", "cycling"],
            "restriction": "A paraphrase of the closure.",
            "stated_dates": None,
            "supporting_sentence_ids": [focus - 1, focus, focus + 3],
        }
        result = review_draft(draft, self.notice)
        self.assertFalse(result["evidence_checks"]["focused_citations_only"])
        self.assertIn(
            "Travel modes",
            " ".join(result["evidence_checks"]["unsupported_claims"]),
        )
        self.assertEqual(result["fields"], self.reference)
        self.assertEqual(
            result["supporting_sentences"][0]["text"],
            self.notice["focus_quote"],
        )

    def test_parking_dates_are_not_applied_to_footpath(self):
        draft = {
            **self.reference,
            "stated_dates": "oktober-november 2026 til sommeren 2027",
        }
        result = review_draft(draft, self.notice)
        self.assertFalse(result["evidence_checks"]["date_claim_supported"])
        self.assertIsNone(result["fields"]["stated_dates"])
        self.assertIn(
            "parking dates do not qualify",
            " ".join(result["evidence_checks"]["corrections"]),
        )

    def test_citation_must_exist_in_saved_notice(self):
        draft = {**self.reference, "supporting_sentence_ids": [999]}
        with self.assertRaisesRegex(RuntimeError, "outside the saved notice"):
            review_draft(draft, self.notice)

    def test_confirmation_precedes_python_assessment_and_preserves_distances(self):
        workspace = Workspace(ROOT, FakeOpener())
        with self.assertRaisesRegex(ValueError, "explicitly confirm"):
            workspace.assess(koigen_request(False))
        result = workspace.assess(koigen_request(True))
        row = result["journeys"][0]
        self.assertEqual(
            (row["baseline_metres"], row["metres"], row["change_metres"]),
            (323, 593, 270),
        )
        self.assertTrue(result["modeled_section_confirmation"])

    def test_saved_notice_uses_one_bounded_model_request(self):
        opener = FakeOpener(koigen_reply())
        result = Workspace(ROOT, opener).draft_koigen_notice({"notice_id": "hamar-koigen-footpath"})
        self.assertEqual(result["state"], "success")
        self.assertEqual(opener.calls, 1)
        self.assertEqual(result["diagnostics"]["requests_made"], 1)
        self.assertEqual(result["evidence_checks"]["unsupported_claims"], [])

    def test_ollama_unavailable_does_not_claim_a_draft(self):
        opener = FakeOpener(error=URLError("refused"))
        result = Workspace(ROOT, opener).draft_koigen_notice({"notice_id": "hamar-koigen-footpath"})
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["failure"]["kind"], "ollama_unavailable")
        self.assertEqual(opener.calls, 1)
        self.assertNotIn("fields", result)


if __name__ == "__main__":
    unittest.main()
