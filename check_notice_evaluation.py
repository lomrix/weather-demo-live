"""Offline checks of the evaluation contract; fake responses are not AI results."""

import copy
import json
from pathlib import Path
import unittest

from harness.notice_draft import build_prompt, extract_notice
from harness.notice_evaluation import (
    LIMITATIONS, evaluate, keyword_baseline, load_cases, markdown_report,
    score_draft, summarize, validate_draft,
)

ROOT = Path(__file__).resolve().parent


class Response:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.raw[:limit]


class NoticeEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.manifest_hash = load_cases(ROOT)

    def test_sources_are_separate_and_references_quote_cited_text(self):
        self.assertEqual(len(self.cases), 4)
        self.assertEqual(sum(case["kind"] == "saved_real_notice" for case in self.cases), 1)
        self.assertEqual(len(self.manifest_hash), 64)
        self.assertEqual(len(self.cases[0]["source"]["file_sha256"]), 64)
        for case in self.cases:
            self.assertEqual(score_draft(case["reference"], case)["matched_fields"], 4)

    def test_extraction_inputs_do_not_contain_gold_answers(self):
        for case in self.cases:
            self.assertEqual(set(case["input"]), {"focus", "sentences"})
        notice = {"focus": "Example", "sentences": ["Source."],
                  "hand_reference": {"location": "SECRET GOLD ANSWER"}}
        self.assertNotIn("SECRET GOLD ANSWER", build_prompt(notice))

    def test_offline_baseline_makes_zero_requests(self):
        def forbidden(*_args, **_kwargs):
            self.fail("Offline baseline contacted a model")
        rows = evaluate(self.cases, "baseline", [], opener=forbidden)
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(row["requests_made"] for row in rows), 0)

    def test_extraction_preserves_raw_answer_without_correction(self):
        case = self.cases[0]
        wrong = {**case["reference"], "stated_dates": "parking dates", "travel_modes": ["cycling"]}
        calls = []
        def opener(request, timeout):
            calls.append(json.loads(request.data))
            self.assertEqual(timeout, 90)
            return Response({"response": json.dumps(wrong), "prompt_eval_count": 50,
                             "eval_count": 20, "done": True})
        result = extract_notice(case["input"], opener=opener, model="test-model:3b")
        self.assertEqual(result["model_draft"], wrong)
        self.assertEqual(calls[0]["model"], "test-model:3b")
        self.assertEqual(result["diagnostics"]["eval_count"], 20)
        self.assertNotIn("hand_reference", calls[0]["prompt"])

    def test_request_cap_is_checked_before_any_request(self):
        def forbidden(*_args, **_kwargs):
            self.fail("Request made before cap rejection")
        with self.assertRaisesRegex(ValueError, "No requests made"):
            evaluate(self.cases, "live", ["one", "two"], max_requests=1, opener=forbidden)

    def test_live_mode_requires_explicit_models(self):
        with self.assertRaisesRegex(ValueError, "explicit model"):
            evaluate(self.cases, "live", [])

    def test_invalid_citations_and_types_fail_instead_of_scoring(self):
        base = self.cases[0]["reference"]
        for bad in ([999], [True], [1, 1], []):
            with self.subTest(ids=bad), self.assertRaises(ValueError):
                score_draft({**base, "supporting_sentence_ids": bad}, self.cases[0])
        for modes in (["flying"], ["walking", "walking"], [None]):
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                validate_draft({**base, "travel_modes": modes}, 20)

    def test_missing_dates_and_unsupported_date_claims_are_separate(self):
        real = self.cases[0]
        self.assertFalse(score_draft(real["reference"], real)["unexpected_date_claim"])
        wrong = score_draft({**real["reference"], "stated_dates": "sommeren 2027"}, real)
        self.assertTrue(wrong["unexpected_date_claim"])
        dated = self.cases[1]
        missing = score_draft({**dated["reference"], "stated_dates": None}, dated)
        self.assertIn("stated_dates", missing["missing_required_fields"])
        self.assertFalse(missing["unexpected_date_claim"])

    def test_quote_presence_does_not_count_as_reference_correctness(self):
        case = self.cases[0]
        wrong = {**case["reference"], "location": "Mjøsa"}
        result = score_draft(wrong, case)
        self.assertTrue(result["quote_checks"]["location"])
        self.assertIn("location", result["reference_mismatches"])
        self.assertNotIn("unsupported_claims", result)

    def test_whitespace_is_normalised_and_input_is_not_modified(self):
        case = self.cases[0]
        original = copy.deepcopy(case)
        draft = {**case["reference"], "location": "  " + case["reference"]["location"].replace(" ", "\n")}
        self.assertTrue(score_draft(draft, case)["exact_case"])
        keyword_baseline(case["input"])
        self.assertEqual(case, original)

    def test_failed_model_requests_remain_in_denominator(self):
        def offline(*_args, **_kwargs):
            raise OSError("simulated outage")
        rows = evaluate(self.cases[:1], "live", ["fake"], opener=offline)
        summary = next(item for item in summarize(rows) if item["method"] == "fake")
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(summary["total_fields"], 4)
        self.assertEqual(summary["matched_fields"], 0)
        self.assertEqual(rows[1]["requests_made"], 1)

    def test_real_and_synthetic_scores_are_never_pooled(self):
        rows = evaluate(self.cases, "baseline", [])
        summary = summarize(rows)
        self.assertEqual({item["kind"] for item in summary}, {"saved_real_notice", "synthetic"})
        report = markdown_report({"mode": "baseline", "requests_made": 0,
                                  "generated_at": "test", "results": rows, "summary": summary})
        self.assertIn("not held-out", report)
        self.assertIn("Corrected UI fields are excluded", report)
        self.assertTrue(LIMITATIONS)

    def test_saved_live_run_scores_recompute_offline(self):
        folder = ROOT / "fixtures/notice-evaluation/runs/2026-11-19"
        report = json.loads((folder / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "live")
        self.assertEqual(report["requests_made"], 8)
        self.assertEqual(len(report["manifest_sha256"]), 64)
        cases = {case["id"]: case for case in self.cases}
        for row in report["results"]:
            self.assertEqual(score_draft(row["draft"], cases[row["case_id"]]), row["score"])
        self.assertEqual(summarize(report["results"]), report["summary"])
        for case in report["cases"]:
            self.assertEqual(case["prompt_sha256"], cases[case["id"]]["prompt_sha256"])
            self.assertEqual(case["input"], cases[case["id"]]["input"])
            self.assertEqual(case["reference"], cases[case["id"]]["reference"])
        # Preserve historical byte hashes without assuming identical Git checkout
        # line endings or preventing future evaluator revisions. Prompts, inputs,
        # references and recomputed scores above are the portable replay contract.
        for key in ("extractor_sha256", "evaluator_sha256"):
            self.assertRegex(report[key], r"^[0-9a-f]{64}$")
        models = json.loads((folder / "installed-models.json").read_text(encoding="utf-8-sig"))
        self.assertEqual({item["name"] for item in models["models"]}, {"qwen2.5:3b", "llama3.2:3b"})
        self.assertTrue(all(len(item["digest"]) == 64 for item in models["models"]))


if __name__ == "__main__":
    unittest.main()
