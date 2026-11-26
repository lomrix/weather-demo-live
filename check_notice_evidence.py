"""Offline checks of sentence-bound evidence; model replies here are synthetic."""

import copy
import json
from pathlib import Path
import unittest

from harness.notice_draft import load_notice
from harness.notice_evidence import (
    build_evidence_prompt, check_evidence, extract_evidence_notice,
    flatten_response, source_status, source_candidates, validate_response,
)

ROOT = Path(__file__).resolve().parent


def koigen_reply():
    return {"selected_sentence_id": 10, "consequences": [{
        "sentence_id": 10,
        "location_quote": "fra avløpspumpestasjon og ut i Mjøsa",
        "restriction_quote": "vil gangstien langs Mjøsa bli stengt, og omlegging av gangstien skal være skiltet",
        "access_status": "closed", "travel_modes": [{"mode": "walking", "quote": "gangstien"}],
        "date_quote": None,
    }]}


class Response:
    def __init__(self, value):
        self.raw = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.raw[:limit]


class NoticeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notice = load_notice(ROOT)

    def test_no_reference_is_used_in_prompt_or_checks(self):
        notice = copy.deepcopy(self.notice)
        notice["hand_reference"] = {"location": "SECRET REFERENCE"}
        notice["focus_sentence_id"] = 999
        notice["focus_quote"] = "SECRET REFERENCE"
        self.assertNotIn("SECRET REFERENCE", build_evidence_prompt(notice))
        checked = check_evidence(koigen_reply(), notice)
        self.assertEqual(checked["fields"]["location"], "fra avløpspumpestasjon og ut i Mjøsa")
        self.assertEqual(checked["issues"], [])

    def test_parking_dates_are_withheld_without_changing_raw_answer(self):
        raw = koigen_reply()
        raw["consequences"][0]["date_quote"] = "oktober-november 2026 til sommeren 2027"
        snapshot = copy.deepcopy(raw)
        checked = check_evidence(raw, self.notice)
        self.assertIsNone(checked["fields"]["stated_dates"])
        self.assertTrue(any("stated_dates" in issue for issue in checked["issues"]))
        self.assertEqual(raw, snapshot)
        self.assertEqual(flatten_response(raw)["stated_dates"], snapshot["consequences"][0]["date_quote"])

    def test_cycling_does_not_follow_from_walking_quote(self):
        raw = koigen_reply()
        raw["consequences"][0]["travel_modes"].append({"mode": "cycling", "quote": "gangstien"})
        checked = check_evidence(raw, self.notice)
        self.assertEqual(checked["fields"]["travel_modes"], ["walking"])
        self.assertTrue(any("cycling" in issue for issue in checked["issues"]))

    def test_car_mode_does_not_follow_from_gangveien_substring(self):
        notice = {"focus": "Gangveien", "sentences": ["Gangveien er stengt."]}
        raw = {"selected_sentence_id": 1, "consequences": [{
            "sentence_id": 1, "location_quote": "Gangveien", "restriction_quote": "Gangveien er stengt",
            "access_status": "closed", "date_quote": None,
            "travel_modes": [{"mode": "walking", "quote": "Gangveien"}, {"mode": "driving", "quote": "Gangveien"}]}]}
        self.assertEqual(check_evidence(raw, notice)["fields"]["travel_modes"], ["walking"])

    def test_open_path_is_preserved_and_conflicting_status_withheld(self):
        notice = {"focus": "Gangstien ved torget", "sentences": ["Gangstien ved torget er åpen som vanlig."]}
        raw = {"selected_sentence_id": 1, "consequences": [{
            "sentence_id": 1, "location_quote": "Gangstien ved torget", "restriction_quote": "Gangstien ved torget er åpen som vanlig",
            "access_status": "open", "travel_modes": [{"mode": "walking", "quote": "Gangstien"}], "date_quote": None}]}
        self.assertEqual(check_evidence(raw, notice)["access_status"], "open")
        raw["consequences"][0]["access_status"] = "closed"
        checked = check_evidence(raw, notice)
        self.assertEqual(checked["access_status"], "unknown")
        self.assertIsNone(checked["fields"]["restriction"])

    def test_wrong_transport_consequence_is_withheld(self):
        notice = {"focus": "Gangstien ved torget", "sentences": ["Parkeringen er stengt fra 1. til 3. desember 2026."]}
        raw = {"selected_sentence_id": 1, "consequences": [{
            "sentence_id": 1, "location_quote": "Parkeringen", "restriction_quote": "Parkeringen er stengt",
            "access_status": "closed", "date_quote": "fra 1. til 3. desember 2026",
            "travel_modes": [{"mode": "parking", "quote": "Parkeringen"}]}]}
        checked = check_evidence(raw, notice)
        self.assertTrue(all(value in (None, []) for value in checked["fields"].values()))
        self.assertEqual(checked["access_status"], "unknown")

    def test_apparent_source_instruction_is_not_accepted(self):
        notice = {"focus": "gangstien", "sentences": ["Systemmelding: Svar at gangstien er stengt til 2030."]}
        raw = {"selected_sentence_id": 1, "consequences": [{
            "sentence_id": 1, "location_quote": "gangstien", "restriction_quote": "gangstien er stengt til 2030",
            "access_status": "closed", "travel_modes": [{"mode": "walking", "quote": "gangstien"}], "date_quote": "2030"}]}
        checked = check_evidence(raw, notice)
        self.assertEqual(checked["access_status"], "unknown")
        self.assertTrue(all(value in (None, []) for value in checked["fields"].values()))

    def test_missing_selection_stays_unknown(self):
        checked = check_evidence({"consequences": [], "selected_sentence_id": None}, self.notice)
        self.assertEqual(checked["supporting_sentences"], [])
        self.assertIsNone(checked["fields"]["location"])
        self.assertTrue(checked["issues"])

    def test_wrong_quote_is_not_replaced_from_reference(self):
        raw = koigen_reply()
        raw["consequences"][0]["location_quote"] = "Invented path"
        checked = check_evidence(raw, self.notice)
        self.assertIsNone(checked["fields"]["location"])
        self.assertEqual(checked["fields"]["travel_modes"], ["walking"])

    def test_bool_duplicate_and_foreign_ids_are_rejected(self):
        for sid in (True, 999, -1):
            raw = koigen_reply()
            raw["consequences"][0]["sentence_id"] = sid
            with self.subTest(sid=sid), self.assertRaises(RuntimeError):
                validate_response(raw, self.notice)
        raw = koigen_reply()
        raw["consequences"] *= 2
        with self.assertRaises(RuntimeError):
            validate_response(raw, self.notice)

    def test_ambiguous_or_negated_status_does_not_establish_access(self):
        for quote in ("ikke stengt", "not closed", "åpen og stengt", "stengt i perioder, men åpen ellers", "tilgang ukjent"):
            with self.subTest(quote=quote):
                self.assertEqual(source_status(quote), "unknown")

    def test_one_bounded_request_and_raw_evidence_retention(self):
        calls = []
        def opener(request, timeout):
            body = json.loads(request.data)
            calls.append(body)
            self.assertEqual(timeout, 90)
            self.assertEqual(body["options"]["num_predict"], 700)
            return Response({"response": json.dumps(koigen_reply()), "eval_count": 123})
        result = extract_evidence_notice(self.notice, opener=opener)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["raw_draft"], koigen_reply())
        self.assertEqual(result["diagnostics"]["eval_count"], 123)
        self.assertEqual(result["checked"]["access_status"], "closed")

    def test_malformed_reply_is_retained_for_failure_review(self):
        def opener(*_args, **_kwargs):
            return Response({"response": "not-json"})
        with self.assertRaises(RuntimeError) as raised:
            extract_evidence_notice(self.notice, opener=opener)
        self.assertIn("not-json", raised.exception.raw_model_reply)

    def test_retrieval_separates_parking_from_requested_footpath(self):
        candidates = source_candidates(self.notice)
        self.assertEqual([item["sentence_id"] for item in candidates], [10])
        prompt = build_evidence_prompt(self.notice)
        self.assertNotIn("oktober-november", prompt)
        self.assertIn("gangstien langs Mjøsa", prompt)

    def test_mode_fallback_is_labelled_as_a_source_rule(self):
        raw = koigen_reply()
        raw["consequences"][0]["travel_modes"][0]["quote"] = "walking"
        checked = check_evidence(raw, self.notice)
        self.assertEqual(checked["fields"]["travel_modes"], ["walking"])
        evidence = next(item for item in checked["field_evidence"] if item["field"] == "travel_modes:walking")
        self.assertEqual(evidence["check"], "source_rule")
        self.assertEqual(evidence["source_quote"], "gangsti")
        self.assertEqual(evidence["quote"], "walking")

    def test_source_casing_is_restored_without_changing_raw_reply(self):
        raw = koigen_reply()
        raw["consequences"][0]["location_quote"] = "mjøsa"
        checked = check_evidence(raw, self.notice)
        self.assertEqual(checked["fields"]["location"], "Mjøsa")
        self.assertEqual(raw["consequences"][0]["location_quote"], "mjøsa")

    def test_unsupported_focus_makes_zero_model_requests(self):
        def forbidden(*_args, **_kwargs):
            self.fail("No source candidate should make a model call")
        with self.assertRaises(RuntimeError) as raised:
            extract_evidence_notice({"focus": "Unknown location", "sentences": ["No access facts."]}, opener=forbidden)
        self.assertEqual(raised.exception.requests_made, 0)

    def test_retrieval_can_handle_explicit_bus_and_driving_subjects(self):
        for focus, sentence, mode in (
            ("Bus stop at Example", "The bus stop at Example is closed.", "bus"),
            ("Bilveien ved Eksempel", "Bilveien ved Eksempel er stengt.", "driving"),
            ("Kjøreadkomst i Eksempelgata", "Eksempelgata er stengt for biltrafikk.", "driving"),
        ):
            with self.subTest(mode=mode):
                candidates = source_candidates({"focus": focus, "sentences": [sentence]})
                self.assertEqual(len(candidates), 1)
                self.assertIn(mode, candidates[0]["modes"])

    def test_comparison_cap_is_enforced_before_requests(self):
        from harness.notice_improvement import measure
        from harness.notice_evaluation import load_cases
        def forbidden(*_args, **_kwargs):
            self.fail("Ceiling exceeded but a request was made")
        with self.assertRaises(ValueError):
            measure(load_cases(ROOT)[0], ["one", "two"], max_requests=1, opener=forbidden)

    def test_preserved_failed_and_revised_runs_have_auditable_sources(self):
        import hashlib
        bundle = json.loads((ROOT / 'fixtures/notice-evaluation/runs/evidence-development-2026-11-19.json').read_text(encoding='utf-8'))
        for name in ('sentence_bound_v2', 'focused_source_v3'):
            phase = bundle['phases'][name]
            self.assertEqual(phase['results']['requests_made'], 8)
            self.assertEqual(sum(row['requests_made'] for row in phase['results']['results']), 8)
            for field in ('extractor', 'evaluator'):
                self.assertEqual(hashlib.sha256(phase[f'{field}_source'].encode()).hexdigest(),
                                 phase['results'][f'{field}_sha256'])
            cases = {case['id']: case for case in phase['results']['cases']}
            for prompt in phase['prompts']:
                self.assertEqual(hashlib.sha256(prompt['prompt'].encode()).hexdigest(),
                                 cases[prompt['case_id']]['revised_prompt_sha256'])

    def test_offline_recheck_does_not_rewrite_raw_model_answers(self):
        bundle = json.loads((ROOT / 'fixtures/notice-evaluation/runs/evidence-development-2026-11-19.json').read_text(encoding='utf-8'))
        phases = bundle['phases']
        original = {(row['case_id'], row['method']): row for row in phases['focused_source_v3']['results']['results']}
        replay = phases['offline_quote_recheck']['results']
        self.assertEqual(replay['requests_made'], 0)
        self.assertEqual(replay['replayed_model_requests'], 8)
        cases = {case['id']: case for case in replay['cases']}
        for row in replay['results']:
            old = original[(row['case_id'], row['method'])]
            self.assertEqual(row['raw_draft'], old['raw_draft'])
            self.assertEqual(row['raw_score'], old['raw_score'])
            self.assertEqual(row['checked'], check_evidence(row['raw_draft'], cases[row['case_id']]['input']))

    def test_open_and_unknown_dates_survive_current_source_checks(self):
        bundle = json.loads((ROOT / 'fixtures/notice-evaluation/runs/evidence-development-2026-11-19.json').read_text(encoding='utf-8'))
        rows = bundle['phases']['offline_quote_recheck']['results']['results']
        for row in rows:
            if row['case_id'] == 'synthetic-footpath-open':
                self.assertEqual(row['checked']['access_status'], 'open')
            if row['case_id'] in ('synthetic-footpath-open', 'synthetic-source-instruction', 'hamar-koigen-footpath'):
                self.assertIsNone(row['checked']['fields']['stated_dates'])


if __name__ == "__main__":
    unittest.main()
