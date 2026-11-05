"""Offline planning-workspace service for the fixed Hamar cases.

Browser input is untrusted: every request is reduced to a small validated
structure that refers to fixed case, section and candidate IDs. Python owns all
routes, distances and candidate geometry. The only network use is the single
bounded local Ollama request made by comparison mode.
"""

import hashlib
import json
import re
import threading
from datetime import date
from pathlib import Path
from urllib.request import urlopen

try:
    from .import_hamar_osm import import_scenario
    from .ollama_scenario import (
        MAX_RESPONSE_BYTES, MODEL, OLLAMA_URL, TIMEOUT_SECONDS, run_comparison,
    )
    from .project_scenario import DATE_RULE, assess_projects, parse_date
    from .scenario_compare import shortest_route
except ImportError:
    from import_hamar_osm import import_scenario
    from ollama_scenario import (
        MAX_RESPONSE_BYTES, MODEL, OLLAMA_URL, TIMEOUT_SECONDS, run_comparison,
    )
    from project_scenario import DATE_RULE, assess_projects, parse_date
    from scenario_compare import shortest_route


ROOT = Path(__file__).resolve().parent.parent
MAX_PROJECTS = 4
MAX_QUESTION = 400
MAX_NAME = 60
MAX_SECTIONS = 60
REQUEST_KEYS = {"case_id", "assessment_date", "projects", "question"}
PROJECT_KEYS = {"name", "start_date", "end_date", "sections", "hypothetical"}

CASES = {
    "ringgata-ankerskogen": {
        "scenario": "hamar-ringgata-ankerskogen.json",
        "osm": "ringgata.osm",
        "label": "Ringgata junction area to Ankerskogen",
        "summary": "Walking from a mapped Ringgata crossing to a path beside Ankerskogen park.",
        "journeys": {
            "junction-area-to-ankerskogen": ("Ringgata crossing", "Ankerskogen park path"),
        },
        "closure_label": "Verified closure: Ringgata cycleway section",
    },
    "furubergvegen-masabekkvegen": {
        "scenario": "hamar-furubergvegen-masabekkvegen.json",
        "osm": "furubergvegen-masabekkvegen.osm",
        "label": "Furubergvegen and Måsåbekkvegen junction",
        "summary": "Walking from a mapped junction crossing to two connected cycle paths.",
        "journeys": {
            "junction-to-north-path": ("Junction crossing", "North cycle path"),
            "junction-to-further-path": ("Junction crossing", "Further cycle path"),
        },
        "closure_label": "Verified closure: mapped junction crossing",
    },
}


class BusyError(Exception):
    """A model comparison is already running."""


class Recorder:
    """Wrap an opener, count requests and keep the raw bytes that were read."""

    def __init__(self, opener):
        self.opener = opener
        self.calls = 0
        self.raw = None

    def __call__(self, request, timeout=None):
        self.calls += 1
        return _RecordedResponse(self.opener(request, timeout=timeout), self)


class _RecordedResponse:
    def __init__(self, inner, recorder):
        self.inner = inner
        self.recorder = recorder
        self.entered = None

    def __enter__(self):
        self.entered = self.inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self.inner.__exit__(*exc)

    def read(self, size=-1):
        data = self.entered.read(size)
        self.recorder.raw = data
        return data


def _title(identifier):
    return identifier.replace("-", " ").capitalize()


def _clean_text(value, label, limit, required=True):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    text = " ".join(value.split())
    if required and not text:
        raise ValueError(f"{label} is required")
    if len(text) > limit:
        raise ValueError(f"{label} must be at most {limit} characters")
    if not text.isprintable():
        raise ValueError(f"{label} contains unsupported characters")
    return text


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class Workspace:
    def __init__(self, root=ROOT, opener=urlopen):
        self.root = Path(root)
        self.opener = opener
        self._busy = threading.Lock()
        manifest = json.loads(
            (self.root / "fixtures" / "maps" / "manifest.json").read_text(encoding="utf-8")
        )
        self.cases = {
            case_id: self._load_case(case_id, config, manifest)
            for case_id, config in CASES.items()
        }

    def _load_case(self, case_id, config, manifest):
        osm = self.root / "fixtures" / "maps" / config["osm"]
        expected = manifest["fixtures"][config["osm"]]
        # The manifest hash is of the LF form; Git on Windows may check out CRLF.
        digest = hashlib.sha256(osm.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if digest != expected["sanitized_fixture_sha256"]:
            raise ValueError(f"{config['osm']} does not match the manifest checksum")
        template = self.root / "fixtures" / "scenarios" / config["scenario"]
        scenario = import_scenario(osm, template)
        extract = scenario["metadata"]["map_extract"]
        extract.get("downloaded_input", {}).pop("path", None)
        walking = [link for link in scenario["network"] if "walking" in link["modes"]]
        links = {link["id"]: link for link in walking}
        nodes = extract["route_map"]["node_coordinates"]
        candidates = {candidate["id"]: candidate for candidate in scenario["candidates"]}
        for candidate in candidates.values():
            candidate["label"] = _title(candidate["id"])
        journeys = []
        for journey in scenario["journeys"]:
            names = config["journeys"].get(journey["id"])
            origin_name, destination_name = names or ("Start", "Destination")
            baseline = shortest_route(scenario["network"], journey["origin"], journey["destination"])
            journeys.append({
                "id": journey["id"],
                "label": f"{origin_name} to {destination_name}",
                "origin": {"id": journey["origin"], "label": origin_name,
                           "coordinates": nodes[journey["origin"]]},
                "destination": {"id": journey["destination"], "label": destination_name,
                                "coordinates": nodes[journey["destination"]]},
                "baseline_metres": baseline["metres"],
                "evidence": journey.get("evidence", {}),
            })
        sections = self._sections(scenario, links, config)
        return {
            "id": case_id,
            "config": config,
            "scenario": scenario,
            "links": links,
            "nodes": nodes,
            "candidates": candidates,
            "journeys": journeys,
            "journey_ids": {journey["id"] for journey in journeys},
            "sections": sections,
            "section_ids": {section["id"]: section for section in sections},
            "manifest": expected,
            "attribution": manifest["attribution"],
            "license": manifest["license"],
        }

    @staticmethod
    def _sections(scenario, links, config):
        extract = scenario["metadata"]["map_extract"]
        closure_ids = list(extract["interrupted_link"]["closure_segment_ids"])
        sections = [{
            "id": "verified-closure",
            "label": config["closure_label"],
            "verified": True,
            "link_ids": closure_ids,
            "metres": sum(links[link_id]["metres"] for link_id in closure_ids),
        }]
        between = {}
        for link in links.values():
            for pair in ((link["from"], link["to"]), (link["to"], link["from"])):
                if pair not in between or link["metres"] < between[pair]["metres"]:
                    between[pair] = link
        taken = set(closure_ids)
        by_way = {}
        for journey in scenario["journeys"]:
            path = shortest_route(
                scenario["network"], journey["origin"], journey["destination"]
            )["path"]
            for pair in zip(path, path[1:]):
                link = between[pair]
                if link["id"] in taken:
                    continue
                taken.add(link["id"])
                way = link["source"].rsplit("/", 1)[-1]
                by_way.setdefault(way, []).append(link)
        for index, (way, way_links) in enumerate(by_way.items(), 1):
            if index > MAX_SECTIONS:
                break
            sections.append({
                "id": f"route-section-{index}",
                "label": f"Route section {index}",
                "verified": False,
                "way_id": way,
                "link_ids": [link["id"] for link in way_links],
                "metres": sum(link["metres"] for link in way_links),
            })
        return sections

    def get_case(self, case_id):
        case = self.cases.get(case_id) if isinstance(case_id, str) else None
        if case is None:
            raise LookupError("Unknown case")
        return case

    def index(self):
        return {
            "today": date.today().isoformat(),
            "mode": {"supported": ["walking"], "note": "Walking only for now; other modes are planned."},
            "ai": {"model": MODEL, "endpoint": OLLAMA_URL, "timeout_seconds": TIMEOUT_SECONDS},
            "cases": [
                {"id": case["id"], "label": case["config"]["label"],
                 "summary": case["config"]["summary"]}
                for case in self.cases.values()
            ],
        }

    def case_payload(self, case_id):
        case = self.get_case(case_id)
        scenario = case["scenario"]
        metadata = scenario["metadata"]
        extract = metadata["map_extract"]
        interrupted = extract["interrupted_link"]
        manifest = case["manifest"]
        evidence = {
            "scenario_id": metadata["id"],
            "fixture": {
                "file": f"fixtures/maps/{case['config']['osm']}",
                "sha256": manifest["sanitized_fixture_sha256"],
                "original_download_sha256": manifest["original_download_sha256"],
                "source_url": manifest["source_url"],
                "retrieved_at": manifest["retrieved_at"],
                "license": case["license"],
                "attribution": case["attribution"],
            },
            "planning_source": metadata.get("planning_source") or metadata.get("petition", {}).get("url"),
            "interrupted_way": {
                "way_id": interrupted["way_id"],
                "from_node": interrupted["from"],
                "to_node": interrupted["to"],
                "tags": interrupted.get("tags", {}),
                "closure_segment_ids": interrupted["closure_segment_ids"],
            },
            "unknowns": list(metadata.get("unknowns", [])) + list(extract.get("unknowns", [])),
            "walking_way_count": extract.get("walking_way_count"),
            "route_node_ids": {
                journey["id"]: [journey["origin"]["id"], journey["destination"]["id"]]
                for journey in case["journeys"]
            },
            "journey_evidence": {j["id"]: j["evidence"] for j in case["journeys"]},
        }
        return {
            "id": case["id"],
            "label": case["config"]["label"],
            "summary": case["config"]["summary"],
            "nodes": case["nodes"],
            "links": [
                [link["id"], link["from"], link["to"], link["metres"]]
                for link in case["links"].values()
            ],
            "journeys": [
                {key: journey[key] for key in ("id", "label", "origin", "destination", "baseline_metres")}
                for journey in case["journeys"]
            ],
            "sections": case["sections"],
            "candidates": list(case["candidates"].values()),
            "evidence": evidence,
            "date_rule": DATE_RULE,
        }

    def normalize(self, payload, need_question=False):
        if not isinstance(payload, dict):
            raise ValueError("Request must be a JSON object")
        unknown = set(payload) - REQUEST_KEYS
        if unknown:
            raise ValueError(f"Unsupported fields: {', '.join(sorted(unknown))}")
        try:
            case = self.get_case(payload.get("case_id"))
        except LookupError:
            raise ValueError("Choose one of the listed Hamar cases") from None
        when = parse_date(payload.get("assessment_date"), "assessment date")
        raw_projects = payload.get("projects")
        if not isinstance(raw_projects, list) or not 1 <= len(raw_projects) <= MAX_PROJECTS:
            raise ValueError(f"Add between 1 and {MAX_PROJECTS} projects")
        projects, names = [], set()
        for index, raw in enumerate(raw_projects, 1):
            if not isinstance(raw, dict):
                raise ValueError("Each project must be an object")
            extra = set(raw) - PROJECT_KEYS
            if extra:
                raise ValueError(f"Project {index}: unsupported fields: {', '.join(sorted(extra))}")
            if raw.get("hypothetical", True) is not True:
                raise ValueError(f"Project {index}: workspace projects are always hypothetical")
            name = _clean_text(raw.get("name"), f"Project {index} name", MAX_NAME)
            if name.casefold() in names:
                raise ValueError(f"Project names must be unique: {name}")
            names.add(name.casefold())
            sections = raw.get("sections")
            if not isinstance(sections, list) or not sections or len(sections) > MAX_SECTIONS + 1:
                raise ValueError(f"{name}: choose at least one closure section")
            unique = []
            for section_id in sections:
                if not isinstance(section_id, str) or section_id not in case["section_ids"]:
                    raise ValueError(f"{name}: unknown closure section")
                if section_id not in unique:
                    unique.append(section_id)
            start = parse_date(raw.get("start_date"), f"{name}: start date")
            end = parse_date(raw.get("end_date"), f"{name}: end date")
            if end < start:
                raise ValueError(f"{name}: end date {end} is before start date {start}")
            projects.append({
                "id": f"project-{index}", "label": name,
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "section_ids": sorted(unique),
            })
        question = ""
        if need_question or payload.get("question"):
            question = _clean_text(payload.get("question", ""), "Question", MAX_QUESTION, need_question)
        return {"case": case, "date": when.isoformat(), "projects": projects, "question": question}

    @staticmethod
    def fingerprints(norm):
        core = {
            "case": norm["case"]["id"], "date": norm["date"],
            "projects": sorted(
                ({key: project[key] for key in ("label", "start_date", "end_date", "section_ids")}
                 for project in norm["projects"]),
                key=_canonical,
            ),
        }
        assessment = hashlib.sha256(_canonical(core).encode()).hexdigest()
        comparison = hashlib.sha256(
            _canonical({**core, "question": norm["question"]}).encode()
        ).hexdigest()
        return assessment, comparison

    def fingerprint(self, payload):
        try:
            norm = self.normalize(payload)
        except ValueError as exc:
            return {"valid": False, "error": str(exc)}
        assessment, comparison = self.fingerprints(norm)
        return {"valid": True, "assessment_fingerprint": assessment,
                "comparison_fingerprint": comparison}

    def _project_scenario(self, norm):
        case = norm["case"]
        projects = []
        for project in norm["projects"]:
            link_ids = [
                link_id for section_id in project["section_ids"]
                for link_id in case["section_ids"][section_id]["link_ids"]
            ]
            projects.append({
                "id": project["id"], "label": project["label"], "hypothetical": True,
                "start_date": project["start_date"], "end_date": project["end_date"],
                "restrictions": [{"type": "close_links", "mode": "walking", "link_ids": link_ids}],
            })
        scenario = case["scenario"]
        return {
            "metadata": {"id": scenario["metadata"]["id"], "label": case["config"]["label"],
                         "synthetic": False, "offline": True},
            "network": scenario["network"],
            "journeys": [
                {"id": j["id"], "origin": j["origin"], "destination": j["destination"]}
                for j in scenario["journeys"]
            ],
            "projects": projects,
        }

    def assess_normalized(self, norm):
        case = norm["case"]
        scenario = self._project_scenario(norm)
        result = assess_projects(scenario, norm["date"])
        info = result["project_assessment"]
        sections_by_project = {p["id"]: p["section_ids"] for p in norm["projects"]}

        def describe(project):
            return {
                "id": project["id"], "label": project["label"], "hypothetical": True,
                "start_date": project["start_date"], "end_date": project["end_date"],
                "sections": [case["section_ids"][s]["label"] for s in sections_by_project[project["id"]]],
                "closed_link_ids": project["closed_walking_links"],
            }

        active = [describe(p) for p in info["active_projects"]]
        closed = sorted({link for p in active for link in p["closed_link_ids"]})
        rows = []
        for row in result["comparison"]["alternatives"][0]["journeys"]:
            rows.append({
                "journey_id": row["journey_id"],
                "baseline_metres": row["baseline"]["metres"],
                "baseline_path": list(row["baseline"]["path"]),
                "metres": row["route"]["metres"],
                "path": list(row["route"]["path"]),
                "change_metres": row["change_metres"],
                "status": row["status"],
                "contributing_projects": row["contributing_projects"],
                "individual": row["individual_projects"],
                "overlap_effect": row["overlap_effect"],
            })
        assessment_fp, _ = self.fingerprints(norm)
        return {
            "fingerprint": assessment_fp,
            "assessment_date": info["assessment_date"],
            "hypothetical": info["hypothetical"],
            "date_rule": info["date_rule"],
            "mode": "walking",
            "active_projects": active,
            "inactive_projects": [describe(p) for p in info["inactive_projects"]],
            "closed_link_ids": closed,
            "journeys": rows,
        }

    def assess(self, payload):
        return self.assess_normalized(self.normalize(payload))

    def compare(self, payload):
        norm = self.normalize(payload, need_question=True)
        if not self._busy.acquire(blocking=False):
            raise BusyError("A model comparison is already running")
        try:
            assessment = self.assess_normalized(norm)
            _, comparison_fp = self.fingerprints(norm)
            base = {"fingerprint": comparison_fp, "assessment": assessment,
                    "question": norm["question"]}
            if not assessment["closed_link_ids"]:
                return {**base, "state": "failed", "failure": {
                    "kind": "no_active_closure",
                    "message": "No project is active on this date, so there is no closure to mitigate. "
                               "No model request was made.",
                }, "diagnostics": self._diagnostics(None, 0)}
            recorder = Recorder(self.opener)
            try:
                result = run_comparison(
                    norm["case"]["scenario"], norm["question"], "walking",
                    assessment["closed_link_ids"], recorder,
                )
            except RuntimeError as exc:
                kind = "ollama_unavailable" if str(exc).startswith("Ollama unavailable") else "model_reply_invalid"
                return {**base, "state": "failed", "failure": {"kind": kind, "message": str(exc)},
                        "diagnostics": self._diagnostics(recorder, recorder.calls, error=str(exc))}
            except ValueError as exc:
                return {**base, "state": "failed", "failure": {
                    "kind": "model_choice_rejected", "message": str(exc)},
                    "diagnostics": self._diagnostics(recorder, recorder.calls, error=str(exc))}
            diagnostics = self._diagnostics(recorder, recorder.calls)
            if result["kind"] == "clarifying_question":
                return {**base, "state": "clarification", "clarification": result["question"],
                        "diagnostics": diagnostics}
            return {**base, **self._comparison_view(norm["case"], result), "state": "success",
                    "diagnostics": diagnostics}
        finally:
            self._busy.release()

    @staticmethod
    def _diagnostics(recorder, calls, error=None):
        raw = None
        if recorder is not None and recorder.raw is not None:
            text = recorder.raw[:MAX_RESPONSE_BYTES].decode("utf-8", "replace")
            raw = text
            try:
                raw = json.loads(text).get("response", text)
            except (ValueError, AttributeError):
                pass
        return {
            "model": MODEL, "endpoint": OLLAMA_URL, "timeout_seconds": TIMEOUT_SECONDS,
            "requests_made": calls, "raw_model_reply": raw, "error": error,
        }

    @staticmethod
    def _comparison_view(case, result):
        alternatives = result["comparison"]["alternatives"]
        effects = result["impact_summary"]["selected_candidates"]
        options = []
        for slot, (choice, effect, alternative) in enumerate(
            zip(result["proposal"]["options"], effects, alternatives[1:]), 1
        ):
            candidate = case["candidates"][choice["candidate_id"]]
            routes = {row["journey_id"]: row["route"] for row in alternative["journeys"]}
            options.append({
                "slot": slot,
                "candidate": {key: candidate[key] for key in (
                    "id", "label", "from", "to", "metres", "assumption", "site_check", "geometry")},
                "reason": choice["reason"],
                "closure_link_count": len(alternative["closure_link_ids"]),
                "journeys": [{
                    "journey_id": row["journey_id"],
                    "path": list(routes[row["journey_id"]]["path"]),
                    "metres": row["candidate_metres"],
                    "baseline_metres": row["baseline_metres"],
                    "closure_metres": row["closure_metres"],
                    "change_vs_baseline": row["change_vs_baseline"],
                    "change_vs_closure": row["change_vs_closure"],
                    "access_restored": row["access_restored"],
                } for row in effect["journeys"]],
            })
        return {"model": MODEL, "rationale": result["proposal"]["rationale"], "options": options}
