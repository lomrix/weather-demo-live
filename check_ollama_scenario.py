"""Focused checks for the local Ollama scenario workflow."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.ollama_scenario import run
from harness.ollama_scenario import run_comparison


ROOT = Path(__file__).resolve().parent
SCENARIO = json.loads(
    (ROOT / "fixtures" / "scenarios" / "synthetic-access.json").read_text(
        encoding="utf-8"
    )
)
COMPARISON_SCENARIO = json.loads(
    (ROOT / "fixtures" / "scenarios" / "synthetic-comparison.json").read_text(
        encoding="utf-8"
    )
)


class FakeResponse:
    def __init__(self, value):
        self.payload = json.dumps({"response": json.dumps(value)}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.payload


def fake_opener(response):
    def opener(_request, timeout):
        response.timeout = timeout
        return FakeResponse(response)
    return opener


class OllamaScenarioTests(unittest.TestCase):
    def test_comparison_selects_two_candidates_and_calculates_three_cases(self):
        proposal = {
            "kind": "comparison_draft",
            "rationale": "Different sides regain different access.",
            "options": [
                {"candidate_id": "north-temporary-link", "reason": "Restores north access."},
                {"candidate_id": "south-temporary-link", "reason": "Restores south access."},
            ],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            result = run_comparison(
                COMPARISON_SCENARIO,
                "Compare two pedestrian mitigations.",
                "walking",
                ["north-origin-crossing", "north-crossing-destination",
                 "south-origin-crossing", "south-crossing-destination"],
            )
        self.assertIn("proposal", result)
        self.assertEqual(len(result["comparison"]["alternatives"]), 3)
        self.assertEqual(len(result["comparison"]["alternatives"][1]["journeys"]), 2)
        north = result["impact_summary"]["selected_candidates"][0]["journeys"][0]
        self.assertTrue(north["access_restored"])
        self.assertEqual(north["candidate_metres"], 220)
        self.assertEqual(north["change_vs_baseline"], 20)
        self.assertTrue(
            result["impact_summary"]["selected_candidates"][0]["journeys"][1]
            ["unreachable_with_candidate"]
        )

    def test_comparison_rejects_unknown_candidate(self):
        proposal = {
            "kind": "comparison_draft",
            "rationale": "Unknown.",
            "options": [
                {"candidate_id": "unknown", "reason": "No."},
                {"candidate_id": "south-temporary-link", "reason": "Yes."},
            ],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            with self.assertRaisesRegex(ValueError, "unknown candidate"):
                run_comparison(COMPARISON_SCENARIO, "Compare.", "walking", ["north-origin-crossing"],)

    def test_comparison_rejects_duplicate_candidate_selection(self):
        proposal = {
            "kind": "comparison_draft",
            "rationale": "Duplicate.",
            "options": [
                {"candidate_id": "north-temporary-link", "reason": "One."},
                {"candidate_id": "north-temporary-link", "reason": "Same."},
            ],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            with self.assertRaisesRegex(ValueError, "distinct"):
                run_comparison(COMPARISON_SCENARIO, "Compare.", "walking", ["north-origin-crossing"])

    def test_comparison_rejects_model_closure_changes(self):
        proposal = {
            "kind": "comparison_draft",
            "rationale": "Changes closure.",
            "options": [
                {"candidate_id": "north-temporary-link", "reason": "One.", "link_ids": ["north-origin-crossing"]},
                {"candidate_id": "south-temporary-link", "reason": "Two."},
            ],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            with self.assertRaisesRegex(ValueError, "cannot alter"):
                run_comparison(COMPARISON_SCENARIO, "Compare.", "walking", ["north-origin-crossing"])
    def test_confirmed_walking_request_separates_proposal_and_result(self):
        alternative = copy.deepcopy(SCENARIO["alternatives"][0])
        alternative["operations"][1]["links"][0].update({
            "length_basis": "assumption",
            "assumption": "Synthetic test length.",
        })
        proposal = {
            "kind": "draft_alternative",
            "alternative": alternative,
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            result = run(SCENARIO, "Close the crossing for pedestrians.", "walking")
        self.assertEqual(result["kind"], "draft_alternative")
        self.assertIn("proposal", result)
        self.assertEqual(result["comparison"]["alternatives"][0]["journeys"][0]["change_metres"], -10)

    def test_unconfirmed_closure_returns_clarification_without_comparison(self):
        result = run(SCENARIO, "Close the crossing during works.")
        self.assertEqual(result["kind"], "clarifying_question")
        self.assertIsNone(result["comparison"])

    def test_unconfirmed_model_closure_returns_clarification_without_comparison(self):
        proposal = {
            "kind": "draft_alternative",
            "alternative": {
                "id": "model-closure",
                "hypothetical": True,
                "operations": [{
                    "type": "close_links",
                    "mode": "walking",
                    "link_ids": ["home-to-crossing"],
                }],
            },
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            result = run(SCENARIO, "Remove access at the crossing.")
        self.assertEqual(result["kind"], "clarifying_question")
        self.assertIsNone(result["comparison"])

    def test_vehicle_scope_rejects_model_walking_closure(self):
        proposal = {
            "kind": "draft_alternative",
            "alternative": SCENARIO["alternatives"][0],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            with self.assertRaisesRegex(ValueError, "conflicts with confirmed vehicle"):
                run(SCENARIO, "Apply the confirmed closure.", "vehicle")

    def test_closure_draft_is_marked_hypothetical_in_checked_comparison(self):
        alternative = {
            "id": "closure-only",
            "operations": [{
                "type": "close_links",
                "mode": "walking",
                "link_ids": ["home-to-crossing"],
            }],
        }
        proposal = {"kind": "draft_alternative", "alternative": alternative}
        with patch("harness.ollama_scenario._request", return_value=proposal):
            result = run(SCENARIO, "Close the crossing for pedestrians.", "walking")
        self.assertIs(result["proposal"], alternative)
        self.assertNotIn("hypothetical", result["proposal"])
        self.assertTrue(result["comparison"]["alternatives"][0]["hypothetical"])

    def test_added_link_without_length_assumption_stops(self):
        proposal = {
            "kind": "draft_alternative",
            "alternative": SCENARIO["alternatives"][0],
        }
        with patch("harness.ollama_scenario._request", return_value=proposal):
            with self.assertRaisesRegex(ValueError, "explicit assumption"):
                run(SCENARIO, "Close the crossing for pedestrians.", "walking")

    def test_malformed_model_response_stops(self):
        for malformed in ([], None):
            with self.subTest(malformed=malformed), patch(
                "harness.ollama_scenario._request", return_value=malformed
            ):
                with self.assertRaisesRegex(ValueError, "JSON object"):
                    run(SCENARIO, "Suggest an access change.", "walking")

    def test_non_object_operations_and_links_stop_clearly(self):
        cases = (
            ({"kind": "draft_alternative", "alternative": {"operations": {}}}, "operations"),
            ({"kind": "draft_alternative", "alternative": {"operations": [None]}}, "operations"),
            (
                {
                    "kind": "draft_alternative",
                    "alternative": {
                        "hypothetical": True,
                        "operations": [{"type": "add_links", "links": [None]}],
                    },
                },
                "links",
            ),
        )
        for malformed, expected_error in cases:
            with self.subTest(malformed=malformed), patch(
                "harness.ollama_scenario._request", return_value=malformed
            ):
                with self.assertRaisesRegex(ValueError, expected_error):
                    run(SCENARIO, "Suggest an access change.", "walking")

    def test_request_uses_bounded_local_model(self):
        proposal = {
            "kind": "draft_alternative",
            "alternative": SCENARIO["alternatives"][1],
        }
        captured = {}
        def opener(request, timeout):
            captured["body"] = json.loads(request.data)
            captured["timeout"] = timeout
            return FakeResponse(proposal)
        result = run(SCENARIO, "Restrict vehicles only.", "vehicle", opener)
        self.assertEqual(result["comparison"]["alternatives"][0]["journeys"][0]["change_metres"], 0)
        self.assertEqual(captured["body"]["model"], "qwen2.5:3b")
        self.assertEqual(captured["body"]["options"]["num_predict"], 700)
        self.assertEqual(captured["timeout"], 30)
        schema = captured["body"]["format"]
        self.assertEqual(schema["type"], "object")
        self.assertEqual(len(schema["oneOf"]), 2)
        draft = schema["oneOf"][1]["properties"]["alternative"]
        self.assertEqual(draft["properties"]["operations"]["minItems"], 1)

    def test_missing_or_non_array_draft_operations_stop(self):
        proposals = (
            {"kind": "draft_alternative", "alternative": {}},
            {"kind": "draft_alternative", "alternative": {"operations": {}}},
        )
        for proposal in proposals:
            with self.subTest(proposal=proposal), patch(
                "harness.ollama_scenario._request", return_value=proposal
            ):
                with self.assertRaisesRegex(ValueError, "operations must be a list"):
                    run(SCENARIO, "Suggest an access change.", "walking")


if __name__ == "__main__":
    unittest.main()
