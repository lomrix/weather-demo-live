"""Synthetic checks for the Hamar workspace request boundary and stale-result logic.

These use saved fixtures and a fake Ollama opener; no live model call is made.
"""

import json
import re
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))

import hamar_workspace
from workspace_service import Workspace

CASE = "furubergvegen-masabekkvegen"
RINGGATA = "ringgata-ankerskogen"


def project(name="Works A", start="2026-05-01", end="2026-05-31", sections=("verified-closure",)):
    return {"name": name, "start_date": start, "end_date": end,
            "sections": list(sections), "hypothetical": True}


def request(case=CASE, date="2026-05-15", projects=None, question=None):
    body = {"case_id": case, "assessment_date": date,
            "projects": projects if projects is not None else [project()]}
    if question is not None:
        body["question"] = question
    return body


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
        self.reply, self.error, self.calls = reply, error, 0

    def __call__(self, _request, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        raw = self.reply if isinstance(self.reply, bytes) else json.dumps(
            {"response": json.dumps(self.reply)}).encode()
        return FakeResponse(raw)


def two_candidates(case_id=CASE):
    ids = [c["id"] for c in Workspace(ROOT).case_payload(case_id)["candidates"]]
    return ids[:2]


def draft(case_id=CASE):
    first, second = two_candidates(case_id)
    return {"kind": "comparison_draft", "rationale": "Two different connections.",
            "options": [{"candidate_id": first, "reason": "First."},
                        {"candidate_id": second, "reason": "Second."}]}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(ROOT, FakeOpener(draft()))

    def test_both_cases_load_with_verified_fixture(self):
        index = self.ws.index()
        self.assertEqual(index["mode"]["supported"], ["walking"])
        self.assertEqual(len(index["cases"]), 3)
        for case in index["cases"]:
            data = self.ws.case_payload(case["id"])
            self.assertTrue(data["sections"][0]["verified"])
            self.assertNotIn("path", data["evidence"].get("fixture", {}))
            self.assertNotIn(str(ROOT), json.dumps(data))

    def test_known_assessment_numbers(self):
        result = self.ws.assess(request())
        self.assertTrue(result["hypothetical"])
        self.assertEqual([(r["baseline_metres"], r["metres"]) for r in result["journeys"]],
                         [(201, 362), (241, 402)])
        ringgata = self.ws.assess(request(RINGGATA))
        self.assertEqual((ringgata["journeys"][0]["baseline_metres"], ringgata["journeys"][0]["metres"]),
                         (1384, 2332))

    def custom(self, case=CASE, shift=0.0):
        journey = self.ws.case_payload(case)["journeys"][0]
        a, b = journey["origin"]["coordinates"], journey["destination"]["coordinates"]
        return {"origin": {"lat": a[0] + shift, "lon": a[1]}, "destination": {"lat": b[0], "lon": b[1]}}

    def custom_request(self, custom, **kwargs):
        return {**request(**kwargs), "custom_journey": custom}

    def test_custom_journey_matches_preset_and_keeps_presets(self):
        plain = self.ws.assess(request())
        self.assertIsNone(plain["custom_journey"])
        for case, expected in ((CASE, (201, 362)), (RINGGATA, (1384, 2332))):
            result = self.ws.assess(self.custom_request(self.custom(case), case=case))
            self.assertEqual(result["journeys"][0]["baseline_metres"], expected[0])
            row = result["custom_journey"]["row"]
            self.assertEqual((row["baseline_metres"], row["metres"]), expected)
            self.assertEqual(result["custom_journey"]["status"], "longer")
        with_custom = self.ws.assess(self.custom_request(self.custom()))
        self.assertEqual(with_custom["journeys"], plain["journeys"])

    def test_custom_journey_snaps_nearby_point(self):
        result = self.ws.assess(self.custom_request(self.custom(shift=0.0003)))
        origin = result["custom_journey"]["origin"]
        self.assertEqual(origin["status"], "snapped")
        self.assertGreater(origin["snap_metres"], 0)

    def test_custom_journey_outside_coverage_is_not_a_closure_result(self):
        far = self.custom()
        far["origin"] = {"lat": 60.9, "lon": 11.0}
        result = self.ws.assess(self.custom_request(far))
        view = result["custom_journey"]
        self.assertEqual((view["status"], view["origin"]["reason"]), ("outside_coverage", "outside_extract"))
        self.assertIsNone(view["row"])
        self.assertEqual(len(result["journeys"]), 2)
        resolved = self.ws.resolve_journey({"case_id": CASE, "custom_journey": far})
        self.assertEqual(resolved["sections"], [])

    def test_custom_journey_unreachable_under_closure_is_distinct(self):
        journey = {"origin": self.custom()["origin"], "destination": {"lat": 60.8044664, "lon": 11.0490872}}
        base = self.ws.resolve_journey({"case_id": CASE, "custom_journey": journey})
        self.assertEqual(base["status"], "ready")
        sections = [s["id"] for s in base["sections"]]
        result = self.ws.assess(self.custom_request(journey, projects=[project(sections=sections)]))
        view = result["custom_journey"]
        self.assertEqual(view["status"], "unreachable_under_closures")
        self.assertIsNone(view["row"]["metres"])
        self.assertEqual(view["baseline_metres"], 190)
        self.assertEqual(view["origin"]["status"], "snapped")
        self.assertEqual(view["destination"]["status"], "snapped")

    def test_custom_sections_rejected_without_matching_journey(self):
        with self.assertRaises(ValueError):
            self.ws.assess(request(projects=[project(sections=("custom-section-1",))]))

    def test_custom_fingerprint_and_validation(self):
        one = self.ws.fingerprint(self.custom_request(self.custom()))
        two = self.ws.fingerprint(self.custom_request(self.custom(shift=0.0003)))
        self.assertNotEqual(one["assessment_fingerprint"], two["assessment_fingerprint"])
        self.assertNotEqual(one["assessment_fingerprint"], self.ws.fingerprint(request())["assessment_fingerprint"])
        for bad in ({"origin": {"lat": "x", "lon": 1}, "destination": {"lat": 1, "lon": 1}},
                    {"origin": {"lat": 1, "lon": 1}},
                    {"origin": {"lat": float("nan"), "lon": 1}, "destination": {"lat": 1, "lon": 1}},
                    {"origin": {"lat": 91, "lon": 1}, "destination": {"lat": 1, "lon": 1}},
                    {"origin": {"lat": True, "lon": 1}, "destination": {"lat": 1, "lon": 1}}):
            with self.assertRaises(ValueError):
                self.ws.assess(self.custom_request(bad))

    def test_same_node_custom_journey_is_flagged(self):
        point = self.custom()["origin"]
        result = self.ws.resolve_journey({"case_id": CASE, "custom_journey": {"origin": point, "destination": point}})
        self.assertEqual(result["status"], "same_place")

    def test_inclusive_date_boundaries(self):
        for date, active in (("2026-04-30", 0), ("2026-05-01", 1), ("2026-05-31", 1), ("2026-06-01", 0)):
            result = self.ws.assess(request(date=date))
            self.assertEqual(len(result["active_projects"]), active, date)

    def test_rejects_invalid_input(self):
        bad = [
            request(case="../../etc/passwd"), request(case="C:\\x"), request(case="nope"),
            request(date="2026-13-01"), request(date="tomorrow"),
            request(projects=[project(start="2026-06-01", end="2026-05-01")]),
            request(projects=[project(sections=("unknown-section",))]),
            request(projects=[]), request(projects=[project()] * 2),
            request(projects=[{**project(), "hypothetical": False}]),
            request(projects=[{**project(), "extra": 1}]),
            {**request(), "unexpected": True},
            request(projects=[project(name="x" * 61)]),
        ]
        for payload in bad:
            with self.assertRaises((ValueError, LookupError), msg=str(payload)[:80]):
                self.ws.assess(payload)

    def test_fingerprint_stale_rules(self):
        base = self.ws.fingerprint(request(question="Q one"))
        self.assertTrue(base["valid"])
        self.assertEqual(base, self.ws.fingerprint(request(question="Q one")))
        changed_date = self.ws.fingerprint(request(date="2026-05-16", question="Q one"))
        self.assertNotEqual(base["assessment_fingerprint"], changed_date["assessment_fingerprint"])
        self.assertNotEqual(base["comparison_fingerprint"], changed_date["comparison_fingerprint"])
        changed_section = self.ws.fingerprint(request(
            projects=[project(sections=("verified-closure", self.ws.case_payload(CASE)["sections"][1]["id"]))],
            question="Q one"))
        self.assertNotEqual(base["assessment_fingerprint"], changed_section["assessment_fingerprint"])
        changed_question = self.ws.fingerprint(request(question="Q two"))
        self.assertEqual(base["assessment_fingerprint"], changed_question["assessment_fingerprint"])
        self.assertNotEqual(base["comparison_fingerprint"], changed_question["comparison_fingerprint"])
        self.assertFalse(self.ws.fingerprint(request(date="nope"))["valid"])

    def test_fingerprint_is_order_independent(self):
        a, b = project("A"), project("B", start="2026-05-10", end="2026-05-20")
        one = self.ws.fingerprint(request(projects=[a, b], question="Q"))
        two = self.ws.fingerprint(request(projects=[b, a], question="Q"))
        self.assertEqual(one, two)

    def test_compare_success_keeps_same_closures_and_raw_reply(self):
        opener = FakeOpener(draft())
        ws = Workspace(ROOT, opener)
        result = ws.compare(request(question="Which two connections help?"))
        self.assertEqual(result["state"], "success")
        self.assertEqual(opener.calls, 1)
        self.assertEqual(len(result["options"]), 2)
        closed = len(result["assessment"]["closed_link_ids"])
        self.assertGreater(closed, 0)
        for option in result["options"]:
            self.assertEqual(option["closure_link_count"], closed)
            self.assertTrue(option["candidate"]["geometry"])
        self.assertEqual(json.loads(result["diagnostics"]["raw_model_reply"])["kind"], "comparison_draft")
        self.assertEqual(result["diagnostics"]["requests_made"], 1)

    def test_compare_failures_keep_assessment(self):
        cases = {
            "ollama_unavailable": FakeOpener(error=URLError("refused")),
            "model_reply_invalid": FakeOpener(reply=b"not json at all"),
            "model_choice_rejected": FakeOpener(reply={"kind": "comparison_draft", "rationale": "x", "options": [
                {"candidate_id": "invented", "reason": "r"}, {"candidate_id": "also-invented", "reason": "r"}]}),
        }
        for kind, opener in cases.items():
            result = Workspace(ROOT, opener).compare(request(question="Help?"))
            self.assertEqual(result["state"], "failed", kind)
            self.assertEqual(result["failure"]["kind"], kind)
            self.assertEqual(opener.calls, 1, kind)
            self.assertEqual(result["assessment"]["journeys"][0]["metres"], 362, kind)

    def test_compare_clarification(self):
        opener = FakeOpener({"kind": "clarifying_question", "question": "Which journey matters most?"})
        result = Workspace(ROOT, opener).compare(request(question="Help?"))
        self.assertEqual(result["state"], "clarification")
        self.assertEqual(result["clarification"], "Which journey matters most?")

    def test_no_active_closure_makes_no_model_call(self):
        opener = FakeOpener(draft())
        result = Workspace(ROOT, opener).compare(request(date="2027-01-01", question="Help?"))
        self.assertEqual(result["failure"]["kind"], "no_active_closure")
        self.assertEqual(opener.calls, 0)

    def test_question_required_for_compare(self):
        with self.assertRaises(ValueError):
            self.ws.compare(request())
        with self.assertRaises(ValueError):
            self.ws.compare(request(question="x" * 401))

    def test_concurrent_compare_is_rejected(self):
        ws = Workspace(ROOT, FakeOpener(draft()))
        self.assertTrue(ws._busy.acquire(blocking=False))
        try:
            with self.assertRaises(hamar_workspace.BusyError):
                ws.compare(request(question="Help?"))
        finally:
            ws._busy.release()


class WiderExtractTests(unittest.TestCase):
    WIDER = "hamar-wider-extract"
    RINGGATA_JUNCTION = (60.7988246, 11.0881825)

    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace(ROOT, FakeOpener(draft(cls.WIDER)))
        data = cls.ws.case_payload(cls.WIDER)
        cls.furu = next(j for j in data["journeys"] if j["id"] == "junction-to-north-path")["origin"]["coordinates"]
        cls.sections = {s["id"]: s for s in data["sections"]}

    def cross(self, section_ids):
        projects = [project(sections=section_ids)] if section_ids else []
        body = request(self.WIDER, projects=projects)
        body["custom_journey"] = {
            "origin": {"lat": self.furu[0], "lon": self.furu[1]},
            "destination": {"lat": self.RINGGATA_JUNCTION[0], "lon": self.RINGGATA_JUNCTION[1]},
        }
        return self.ws.assess(body)

    def test_wider_extract_covers_both_areas_and_keeps_preset_numbers(self):
        data = self.ws.case_payload(self.WIDER)
        self.assertEqual((data["coverage"]["minlon"], data["coverage"]["maxlon"]), (11.04, 11.09))
        self.assertGreater(data["coverage"]["walking_node_count"], 4000)
        result = self.ws.assess(request(self.WIDER))
        self.assertEqual([(r["baseline_metres"], r["metres"]) for r in result["journeys"]],
                         [(1384, 2332), (201, 201), (241, 241)])
        self.assertIn("furubergvegen-crossing", self.sections)

    def test_closures_in_each_area_affect_the_cross_area_route(self):
        results = {}
        for name, ids in (("ringgata", ["verified-closure"]), ("furu", ["furubergvegen-crossing"]),
                          ("both", ["verified-closure", "furubergvegen-crossing"])):
            row = self.cross(ids)["custom_journey"]["row"]
            results[name] = (row["baseline_metres"], row["metres"])
        self.assertEqual(results["ringgata"], (2492, 3440))
        self.assertEqual(results["furu"], (2492, 2653))
        self.assertEqual(results["both"], (2492, 3601))

    def test_point_between_areas_is_covered(self):
        view = self.ws.resolve_journey({
            "case_id": self.WIDER,
            "custom_journey": {"origin": {"lat": self.furu[0], "lon": self.furu[1]},
                               "destination": {"lat": 60.7988246, "lon": 11.0881825}}})
        self.assertEqual(view["status"], "ready")
        self.assertGreater(view["baseline_metres"], 2000)


class HttpBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.opener = FakeOpener(draft())
        cls.server = hamar_workspace.WorkspaceServer(0, opener=cls.opener)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, method, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        base = {"Content-Type": "application/json"} if method == "POST" else {}
        base.update(headers or {})
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=base)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_static_whitelist_and_headers(self):
        for path in ("/", "/app.css", "/app.js"):
            status, _, headers = self.call("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        for path in ("/../hamar_workspace.py", "/..%2fREADME.md", "/AGENTS.md", "/workspace/app.js",
                     "/.env", "/api/cases/..%2f..%2fREADME.md", "/api/cases/a/b", "/api/nothing"):
            self.assertEqual(self.call("GET", path)[0], 404, path)

    def test_cases_api(self):
        status, body, _ = self.call("GET", "/api/cases")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["cases"]), 3)
        self.assertEqual(self.call("GET", "/api/cases/unknown")[0], 404)

    def test_post_boundary(self):
        good = request(question="Help?")
        self.assertEqual(self.call("POST", "/api/assess", good)[0], 200)
        self.assertEqual(self.call("POST", "/api/assess", good, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.call("POST", "/api/assess", raw=b"{not json")[0], 400)
        self.assertEqual(self.call("POST", "/api/assess", raw=b"x" * (hamar_workspace.MAX_BODY + 1))[0], 413)
        self.assertEqual(self.call("POST", "/api/assess", request(date="bad"))[0], 400)
        self.assertEqual(self.call("POST", "/api/assess", request(case="../x"))[0], 400)
        self.assertEqual(self.call("POST", "/api/unknown", good)[0], 404)
        self.assertEqual(self.call("POST", "/api/assess", good, {"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.call("POST", "/api/assess", good, {"Host": "evil.example"})[0], 403)
        self.assertEqual(self.call("POST", "/api/assess", good, {"Origin": f"http://127.0.0.1:{self.port}"})[0], 200)

    def test_no_shell_or_path_fields_accepted(self):
        for extra in ({"path": "C:\\Windows"}, {"command": "calc"}, {"osm_path": "x.osm"}):
            self.assertEqual(self.call("POST", "/api/assess", {**request(), **extra})[0], 400)

    def test_compare_over_http_makes_one_request(self):
        before = self.opener.calls
        status, body, _ = self.call("POST", "/api/compare", request(question="Help?"))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["state"], "success")
        self.assertEqual(self.opener.calls - before, 1)


class StaticAssetTests(unittest.TestCase):
    def test_ankerskogen_regression_figures(self):
        reply = {"kind": "comparison_draft", "rationale": "Model prose.", "options": [
            {"candidate_id": "junction-west-connector", "reason": "R1"},
            {"candidate_id": "central-path-connector", "reason": "R2"}]}
        result = Workspace(ROOT, FakeOpener(reply)).compare(request(
            RINGGATA, "2026-05-15", question="Which two connections help?"))
        self.assertEqual(result["state"], "success")
        figures = []
        for option in result["options"]:
            row = option["journeys"][0]
            figures.append((row["metres"], -row["change_vs_closure"], row["change_vs_baseline"]))
        self.assertEqual(figures, [(1477, 855, 93), (1977, 355, 593)])

    def test_model_prose_is_diagnostics_only_in_client(self):
        script = (ROOT / "workspace" / "app.js").read_text(encoding="utf-8")
        card = script[script.index("function optionBlock"):script.index("function renderResults")]
        self.assertNotIn("option.reason", card)
        self.assertNotIn("c.rationale", card)
        self.assertIn("Total walking distance", card)
        self.assertIn("Saved versus closure only", card)
        self.assertIn("Added versus baseline", card)
        self.assertIn("safety, accessibility and construction feasibility", card)
        diagnostics = script[script.index("function renderDiagnostics"):script.index("/* ---------- case loading")]
        self.assertIn("o.reason", diagnostics)
        self.assertIn("c.rationale", diagnostics)
        self.assertIn("raw_model_reply", diagnostics)

    def test_assets_are_offline_and_use_safe_dom_writes(self):
        for name in ("index.html", "app.css", "app.js"):
            text = (ROOT / "workspace" / name).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"https?://[^\s\"')]+", text.replace("http://www.w3.org/2000/svg", "")), [], name)
        script = (ROOT / "workspace" / "app.js").read_text(encoding="utf-8")
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "document.write"):
            self.assertNotIn(forbidden, script)
        html = (ROOT / "workspace" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<style", html)
        self.assertNotRegex(html, r"\son\w+=")
        for text in ("Mapped Hamar case", "Compare options with AI", "Assess projects"):
            self.assertIn(text, html + script)

    def test_client_distinguishes_outside_coverage_from_unreachable(self):
        script = (ROOT / "workspace" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/journey", script)
        self.assertIn("Outside map coverage", script)
        self.assertIn("Unreachable under closures", script)
        self.assertIn("outside loaded map coverage", script)

    def test_client_uses_python_fingerprint_for_staleness(self):
        script = (ROOT / "workspace" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/fingerprint", script)
        self.assertIn("assessment_fingerprint", script)
        self.assertIn("comparison_fingerprint", script)


if __name__ == "__main__":
    unittest.main()
