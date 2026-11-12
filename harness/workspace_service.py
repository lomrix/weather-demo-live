"""Offline planning-workspace service for the fixed Hamar cases.

Browser input is untrusted: every request is reduced to a small validated
structure that refers to fixed case, section and candidate IDs. Python owns all
routes, distances and candidate geometry. The only network use is the single
bounded local Ollama request made by comparison mode.
"""

import hashlib
import json
import math
import re
import threading
from datetime import date
from pathlib import Path
from urllib.request import urlopen

try:
    from .import_driving_osm import import_roads
    from .import_hamar_osm import import_scenario
    from .ollama_scenario import (
        MAX_RESPONSE_BYTES, MODEL, OLLAMA_URL, TIMEOUT_SECONDS, run_comparison,
    )
    from .project_scenario import DATE_RULE, assess_projects, parse_date
    from .scenario_compare import shortest_route
except ImportError:
    from import_driving_osm import import_roads
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
MAX_SNAP_METRES = 75
CUSTOM_ID = "custom"
REQUEST_KEYS = {"case_id", "assessment_date", "projects", "question", "custom_journey"}
PROJECT_KEYS = {"name", "start_date", "end_date", "sections", "hypothetical"}

PUBLISHED_BUS_CASES = {
    "hamar-b21-2026-11-12": "hamar-b21-2026-11-12.json",
    "hamar-b23-2026-11-12": "hamar-b23-2026-11-12.json",
}

CASES = {
    "ringgata-ankerskogen": {
        "scenario": "hamar-ringgata-ankerskogen.json",
        "osm": "ringgata.osm",
        "label": "Ringgata junction area to Ankerskogen",
        "summary": "Walking from a mapped Ringgata crossing to a path beside Ankerskogen park.",
        "journeys": {
            "junction-area-to-ankerskogen": ("Ringgata crossing", "Ankerskogen park path"),
        },
        "closure_label": "Mapped section (basis for the hypothetical closure): Ringgata cycleway section",
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
        "closure_label": "Mapped crossing (basis for the hypothetical closure): junction crossing",
    },
    "hamar-wider-extract": {
        "scenario": "hamar-wider-extract.json",
        "osm": "hamar-wider.osm",
        "label": "Wider Hamar extract: Ringgata to Furubergvegen",
        "summary": "One walking extract covering both mapped areas and the land between them.",
        "journeys": {
            "junction-area-to-ankerskogen": ("Ringgata crossing", "Ankerskogen park path"),
            "junction-to-north-path": ("Junction crossing", "North cycle path"),
            "junction-to-further-path": ("Junction crossing", "Further cycle path"),
        },
        "closure_label": "Ringgata area: mapped cycleway section (basis for the hypothetical closure)",
        "extra_closures": [{
            "id": "furubergvegen-crossing",
            "label": "Furubergvegen area: mapped junction crossing (basis for the hypothetical closure)",
            "way_id": "1482019890",
            "from": "302664786",
            "to": "13591294853",
        }],
    },
}

CASES["hamar-urban"] = {
    **CASES["hamar-wider-extract"],
    "osm": "hamar-urban.osm",
    "label": "Hamar urban-area walking extract",
    "summary": "A rectangular Hamar urban-area extract; not the municipal boundary.",
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


def _parse_point(value, label):
    if not isinstance(value, dict) or set(value) != {"lat", "lon"}:
        raise ValueError(f"{label} must have lat and lon")
    lat, lon = value["lat"], value["lon"]
    for name, number, limit in (("lat", lat, 90), ("lon", lon, 180)):
        if isinstance(number, bool) or not isinstance(number, (int, float)) \
                or not math.isfinite(number) or abs(number) > limit:
            raise ValueError(f"{label} {name} is not a valid coordinate")
    return round(float(lat), 6), round(float(lon), 6)


def _parse_custom(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"origin", "destination"}:
        raise ValueError("Custom journey needs origin and destination")
    return {key: _parse_point(value[key], f"Custom {key}") for key in ("origin", "destination")}


def _distance_metres(a, b):
    scale = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((b[0] - a[0]) * 111320, (b[1] - a[1]) * 111320 * scale)


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
        self.cases["hamar-driving"] = self._load_driving_case(manifest)
        self.bus = json.loads(
            (self.root / "fixtures" / "scenarios" / "synthetic-hamar-bus.json").read_text(encoding="utf-8")
        )
        case = self.get_case(self.bus["case_id"])
        stops = self.bus["stops"]
        ids = [stop["id"] for stop in stops]
        if (self.bus["synthetic"] is not True or len(ids) < 3 or len(set(ids)) != len(ids)
                or self.bus["usual_stop_id"] not in ids
                or self.bus["default_destination_stop_id"] not in ids
                or ids.index(self.bus["usual_stop_id"]) >= ids.index(self.bus["default_destination_stop_id"])):
            raise ValueError("Invalid synthetic bus scenario or stop order")
        if any(node not in case["nodes"] for node in
               [self.bus["origin"]["node_id"]] + [stop["node_id"] for stop in stops]):
            raise ValueError("Synthetic bus points must be on the saved walking network")
        self.published_buses = {
            case_id: self._load_published_bus(filename)
            for case_id, filename in PUBLISHED_BUS_CASES.items()
        }
        self.default_published_bus_id = next(iter(self.published_buses))
        self.published_bus = self.published_buses[self.default_published_bus_id]

    def _load_driving_case(self, manifest):
        filename = "hamar-urban-roads.osm"
        path = self.root / "fixtures" / "maps" / filename
        expected = manifest["fixtures"][filename]
        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if digest != expected["sanitized_fixture_sha256"]:
            raise ValueError(f"{filename} does not match the manifest checksum")
        graph = import_roads(path)
        config = json.loads((self.root / "fixtures" / "scenarios" / "hamar-driving.json").read_text(encoding="utf-8"))
        journey = config["journey"]
        nodes = graph["nodes"]
        links = {link["id"]: link for link in graph["network"]}
        if journey["origin"] not in nodes or journey["destination"] not in nodes:
            raise ValueError("Driving journey endpoints must be on the road network")
        if not config["closure"]["link_ids"] or any(link not in links for link in config["closure"]["link_ids"]):
            raise ValueError("Driving closure must reference mapped car links")
        baseline = shortest_route(graph["network"], journey["origin"], journey["destination"], mode="vehicle")
        if baseline["metres"] is None:
            raise ValueError("Driving journey has no baseline route")
        section = {**config["closure"], "verified": False,
                   "metres": sum(links[link]["metres"] for link in config["closure"]["link_ids"])}
        scenario = {
            "metadata": {"id": config["id"]},
            "network": graph["network"],
            "journeys": [{"id": journey["id"], "origin": journey["origin"], "destination": journey["destination"]}],
        }
        return {
            "id": "hamar-driving", "mode": "vehicle",
            "config": {"label": config["label"], "summary": config["summary"], "osm": filename},
            "scenario": scenario, "links": links, "nodes": nodes,
            "coverage": {**graph["bounds"], "node_count": len(nodes), "link_count": len(links)},
            "candidates": {}, "sections": [section], "section_ids": {section["id"]: section},
            "journeys": [{
                "id": journey["id"], "label": f"{journey['origin_label']} to {journey['destination_label']}",
                "origin": {"id": journey["origin"], "label": journey["origin_label"], "coordinates": nodes[journey["origin"]]},
                "destination": {"id": journey["destination"], "label": journey["destination_label"], "coordinates": nodes[journey["destination"]]},
                "baseline_metres": baseline["metres"],
            }],
            "manifest": expected, "attribution": manifest["attribution"], "license": manifest["license"],
        }

    def _load_published_bus(self, filename):
        published = json.loads(
            (self.root / "fixtures" / "scenarios" / filename).read_text(encoding="utf-8")
        )
        case = self.get_case(published["case_id"])
        ids = [stop["id"] for stop in published["stops"]]
        if (published["synthetic"] is not False or len(ids) != len(set(ids))
                or published["usual_stop_id"] not in ids or published["default_destination_stop_id"] not in ids
                or ids.index(published["usual_stop_id"]) >= ids.index(published["default_destination_stop_id"])
                or published["origin"]["node_id"] not in case["nodes"]):
            raise ValueError("Invalid published bus scenario or stop order")
        for stop in published["stops"]:
            if any(type(stop[key]) is not bool for key in ("for_boarding", "for_alighting", "timing_point")):
                raise ValueError("Published bus stop rules must be explicit")
            point = _parse_point(dict(zip(("lat", "lon"), stop["coordinates"])), "Bus stop")
            snap = self._snap(case, point, "Bus stop")
            stop["node_id"] = snap.get("node_id")
            stop["snap_metres"] = snap.get("snap_metres")
            stop["snap_reason"] = snap.get("reason")
        usual = published["stops"][ids.index(published["usual_stop_id"])]
        destination = published["stops"][ids.index(published["default_destination_stop_id"])]
        if (not usual["for_boarding"] or usual["timing_point"] or not usual["node_id"]
                or not destination["for_alighting"] or destination["timing_point"] or not destination["node_id"]):
            raise ValueError("Published bus scenario needs a mapped boardable usual stop and alightable destination")
        return published

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
        bounds = extract["downloaded_input"]["bounds"]
        coverage = {key: float(bounds[key]) for key in ("minlat", "minlon", "maxlat", "maxlon")}
        coverage["walking_node_count"] = len(nodes)
        coverage["walking_link_count"] = len(links)
        coverage["walking_way_count"] = extract.get("walking_way_count")
        return {
            "id": case_id,
            "config": config,
            "scenario": scenario,
            "links": links,
            "nodes": nodes,
            "coverage": coverage,
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
        between = Workspace._link_between(links)
        taken = set(closure_ids)
        for extra in config.get("extra_closures", []):
            ids = Workspace._way_section(links, extra)
            taken.update(ids)
            sections.append({
                "id": extra["id"],
                "label": extra["label"],
                "verified": True,
                "link_ids": ids,
                "metres": sum(links[link_id]["metres"] for link_id in ids),
            })
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

    @staticmethod
    def _way_section(links, closure):
        way_links = sorted(
            (link for link in links.values()
             if link["source"].rsplit("/", 1)[-1] == closure["way_id"]),
            key=lambda link: int(link["id"].rsplit("-", 1)[-1]),
        )
        selected, active = [], False
        for link in way_links:
            if link["from"] == closure["from"]:
                active = True
            if active:
                selected.append(link["id"])
                if link["to"] == closure["to"]:
                    return selected
        raise ValueError(f"closure section on way {closure['way_id']} is missing")

    @staticmethod
    def _link_between(links):
        between = {}
        for link in links.values():
            for pair in ((link["from"], link["to"]), (link["to"], link["from"])):
                if pair not in between or link["metres"] < between[pair]["metres"]:
                    between[pair] = link
        return between

    @staticmethod
    def _custom_sections(case, path):
        between = Workspace._link_between(case["links"])
        by_way = {}
        for pair in zip(path, path[1:]):
            link = between[pair]
            way = link["source"].rsplit("/", 1)[-1]
            by_way.setdefault(way, {})[link["id"]] = link
        sections = []
        for index, (way, way_links) in enumerate(by_way.items(), 1):
            if index > MAX_SECTIONS:
                break
            sections.append({
                "id": f"custom-section-{index}",
                "label": f"Your route, section {index}",
                "verified": False,
                "custom": True,
                "way_id": way,
                "link_ids": list(way_links),
                "metres": sum(link["metres"] for link in way_links.values()),
            })
        return sections

    @staticmethod
    def _snap(case, point, label):
        coverage = case["coverage"]
        lat, lon = point
        base = {"requested": [lat, lon]}
        if not (coverage["minlat"] <= lat <= coverage["maxlat"]
                and coverage["minlon"] <= lon <= coverage["maxlon"]):
            return {**base, "status": "outside_coverage", "reason": "outside_extract",
                    "message": f"{label} is outside the loaded map extract."}
        node_id, best = None, None
        for candidate, coordinates in case["nodes"].items():
            distance = _distance_metres(point, coordinates)
            if best is None or distance < best:
                node_id, best = candidate, distance
        if best is None or best > MAX_SNAP_METRES:
            return {**base, "status": "outside_coverage", "reason": "no_walking_network_nearby",
                    "message": f"{label} is inside the extract but more than {MAX_SNAP_METRES} m "
                                                   "from the nearest mapped walking node."}
        return {**base, "status": "snapped", "node_id": node_id,
                "snapped": list(case["nodes"][node_id]), "snap_metres": round(best, 1),
                "message": f"{label} snapped to the nearest mapped walking node ({round(best)} m away)."}

    def resolve_custom(self, case, custom):
        origin = self._snap(case, custom["origin"], "Start")
        destination = self._snap(case, custom["destination"], "Destination")
        result = {"id": CUSTOM_ID, "origin": origin, "destination": destination,
                  "sections": [], "baseline_metres": None, "baseline_path": []}
        if origin["status"] != "snapped" or destination["status"] != "snapped":
            result["status"] = "outside_coverage"
            result["message"] = (
                "Not assessed: an endpoint is outside the loaded map coverage. "
                "This is a map-data limit, not a closure result."
            )
        elif origin["node_id"] == destination["node_id"]:
            result["status"] = "same_place"
            result["message"] = "Start and destination snap to the same mapped node; choose points further apart."
        else:
            baseline = shortest_route(
                case["scenario"]["network"], origin["node_id"], destination["node_id"]
            )
            if baseline["metres"] is None:
                result["status"] = "no_baseline_route"
                result["message"] = (
                    "Both points are on the map, but the saved walking network has no route "
                    "between them even without closures (disconnected or unmapped link)."
                )
            else:
                result["status"] = "ready"
                result["message"] = "Both endpoints are inside the map and connected without closures."
                result["baseline_metres"] = baseline["metres"]
                result["baseline_path"] = list(baseline["path"])
                result["sections"] = self._custom_sections(case, baseline["path"])
        return result

    def resolve_journey(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"case_id", "custom_journey"}:
            raise ValueError("Send case_id and custom_journey")
        try:
            case = self.get_case(payload["case_id"])
        except LookupError:
            raise ValueError("Choose one of the listed Hamar cases") from None
        if case.get("mode") == "vehicle":
            raise ValueError("Custom driving journeys are not supported")
        custom = _parse_custom(payload["custom_journey"])
        if custom is None:
            raise ValueError("Custom journey needs origin and destination")
        return self.resolve_custom(case, custom)

    def get_case(self, case_id):
        case = self.cases.get(case_id) if isinstance(case_id, str) else None
        if case is None:
            raise LookupError("Unknown case")
        return case

    def bus_scenario(self, published=False, case_id=None):
        if published:
            if case_id is None:
                case_id = self.default_published_bus_id
            bus = self.published_buses.get(case_id) if isinstance(case_id, str) else None
            if bus is None:
                raise LookupError("Unknown published bus case")
        else:
            bus = self.bus
        case = self.get_case(bus["case_id"])
        origin = bus["origin"]
        return {
            **bus,
            "origin": {**origin, "coordinates": case["nodes"][origin["node_id"]]},
            "stops": [
                stop if published else {**stop, "coordinates": case["nodes"][stop["node_id"]]}
                for stop in bus["stops"]
            ],
        }

    def published_bus_scenario(self, case_id=None):
        return self.bus_scenario(published=True, case_id=case_id)

    def assess_bus(self, payload):
        if not isinstance(payload, dict) or set(payload) not in (
                {"destination_stop_id"}, {"destination_stop_id", "scenario"}):
            raise ValueError("Choose a destination stop")
        scenario = payload.get("scenario", "synthetic")
        if not isinstance(scenario, str):
            raise ValueError("Choose a listed bus scenario")
        if scenario == "synthetic":
            bus = self.bus
        else:
            bus_id = self.default_published_bus_id if scenario == "published" else scenario
            bus = self.published_buses.get(bus_id)
            if bus is None:
                raise ValueError("Choose a listed bus scenario")
        stops = bus["stops"]
        ids = [stop["id"] for stop in stops]
        destination = payload["destination_stop_id"]
        if not isinstance(destination, str) or destination not in ids:
            raise ValueError("Choose a stop on the selected trip")
        usual_index, destination_index = ids.index(bus["usual_stop_id"]), ids.index(destination)
        if destination_index <= usual_index:
            raise ValueError("The destination must be after the usual stop")
        if not bus["synthetic"] and (not stops[destination_index]["for_alighting"]
                                     or stops[destination_index]["timing_point"]
                                     or not stops[destination_index]["node_id"]):
            raise ValueError("Choose an alightable destination within the walking map")
        case = self.get_case(bus["case_id"])
        network = case["scenario"]["network"]
        origin = bus["origin"]["node_id"]
        usual = stops[usual_index]
        normal = shortest_route(network, origin, usual["node_id"])
        choices, outside_coverage, unreachable = [], [], []
        for index, stop in enumerate(stops[:destination_index]):
            if stop["id"] == usual["id"]:
                continue
            if not bus["synthetic"] and (not stop["for_boarding"] or stop["timing_point"]):
                continue
            if not stop["node_id"]:
                outside_coverage.append(stop["id"])
                continue
            route = shortest_route(network, origin, stop["node_id"])
            if route["metres"] is not None:
                choices.append((route["metres"], index, stop["id"], route))
            else:
                unreachable.append(stop["id"])
        alternative = min(choices) if choices else None
        return {
            "destination_stop_id": destination,
            "normal": {"stop_id": usual["id"], **normal},
            "skipped": (
                {"status": "available", "stop_id": alternative[2], **alternative[3]}
                if alternative else
                {"status": "coverage_limited" if outside_coverage else "no_alternative",
                 "stop_id": None, "metres": None, "path": []}
            ),
            "bus_delay": None,
            "outside_coverage_stops": len(outside_coverage),
            "outside_coverage_stop_ids": outside_coverage,
            "unreachable_stop_ids": unreachable,
        }

    def index(self):
        return {
            "today": date.today().isoformat(),
            "mode": {"supported": ["walking", "vehicle"], "note": "Walking and a fixed driving case are supported."},
            "ai": {"model": MODEL, "endpoint": OLLAMA_URL, "timeout_seconds": TIMEOUT_SECONDS},
            "bus_cases": [
                {"id": case_id, "label": f"{bus['service']} · {bus['direction']} · {bus['service_date']}"}
                for case_id, bus in self.published_buses.items()
            ],
            "cases": [
                {"id": case["id"], "label": case["config"]["label"],
                 "summary": case["config"]["summary"]}
                for case in self.cases.values()
            ],
        }

    def case_payload(self, case_id):
        case = self.get_case(case_id)
        if case.get("mode") == "vehicle":
            manifest = case["manifest"]
            return {
                "id": case_id, "mode": "vehicle", "label": case["config"]["label"],
                "summary": case["config"]["summary"], "nodes": case["nodes"], "coverage": case["coverage"],
                "links": [[link["id"], link["from"], link["to"], link["metres"]]
                          for link in case["links"].values()],
                "journeys": case["journeys"], "sections": case["sections"], "candidates": [],
                "evidence": {
                    "scenario_id": case["scenario"]["metadata"]["id"],
                    "fixture": {"file": f"fixtures/maps/{case['config']['osm']}",
                                "sha256": manifest["sanitized_fixture_sha256"],
                                "original_download_sha256": manifest["original_download_sha256"],
                                "source_url": manifest["source_url"], "retrieved_at": manifest["retrieved_at"],
                                "license": case["license"], "attribution": case["attribution"]},
                    "planning_source": "Hypothetical closure, not a published plan.",
                    "unknowns": ["Turn restrictions and conditional rules are not modeled; legal access and road conditions are unverified."],
                },
                "date_rule": DATE_RULE,
            }
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
            "coverage": {**case["coverage"], "snap_metres": MAX_SNAP_METRES},
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
        custom = _parse_custom(payload.get("custom_journey"))
        if custom and case.get("mode") == "vehicle":
            raise ValueError("Custom driving journeys are not supported")
        resolved = self.resolve_custom(case, custom) if custom else None
        section_ids = dict(case["section_ids"])
        if resolved:
            section_ids.update({s["id"]: s for s in resolved["sections"]})
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
            if not isinstance(sections, list) or not sections or len(sections) > 2 * MAX_SECTIONS + 1:
                raise ValueError(f"{name}: choose at least one closure section")
            unique = []
            for section_id in sections:
                if not isinstance(section_id, str) or section_id not in section_ids:
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
        return {"case": case, "date": when.isoformat(), "projects": projects, "question": question,
                "custom": resolved, "custom_request": custom, "section_ids": section_ids}

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
        if norm["custom_request"]:
            core["custom_journey"] = norm["custom_request"]
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
        driving = case.get("mode") == "vehicle"
        projects = []
        for project in norm["projects"]:
            link_ids = list(dict.fromkeys(
                link_id for section_id in project["section_ids"]
                for link_id in norm["section_ids"][section_id]["link_ids"]
            ))
            projects.append({
                "id": project["id"], "label": project["label"], "hypothetical": True,
                "start_date": project["start_date"], "end_date": project["end_date"],
                "restrictions": [{"type": "restrict_links" if driving else "close_links",
                                  "mode": "vehicle" if driving else "walking", "link_ids": link_ids}],
            })
        scenario = case["scenario"]
        journeys = [
            {"id": j["id"], "origin": j["origin"], "destination": j["destination"]}
            for j in scenario["journeys"]
        ]
        custom = norm["custom"]
        if custom and custom["status"] == "ready":
            journeys.append({"id": CUSTOM_ID, "origin": custom["origin"]["node_id"],
                             "destination": custom["destination"]["node_id"]})
        return {
            "metadata": {"id": scenario["metadata"]["id"], "label": case["config"]["label"],
                         "synthetic": False, "offline": True},
            "network": scenario["network"],
            "routing_mode": "vehicle" if driving else "walking",
            "journeys": journeys,
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
                "sections": [norm["section_ids"][s]["label"] for s in sections_by_project[project["id"]]],
                "closed_link_ids": project["restricted_vehicle_links" if case.get("mode") == "vehicle"
                                           else "closed_walking_links"],
            }

        active = [describe(p) for p in info["active_projects"]]
        closed = sorted({link for p in active for link in p["closed_link_ids"]})
        rows, custom_row = [], None
        for row in result["comparison"]["alternatives"][0]["journeys"]:
            item = {
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
            }
            if row["journey_id"] == CUSTOM_ID:
                custom_row = item
            else:
                rows.append(item)
        custom_view = None
        if norm["custom"]:
            custom_view = {key: value for key, value in norm["custom"].items() if key != "sections"}
            custom_view["row"] = custom_row
            if custom_row:
                custom_view["status"] = {
                    "unreachable": "unreachable_under_closures",
                    "longer": "longer", "unchanged": "unchanged",
                }[custom_row["status"]]
        assessment_fp, _ = self.fingerprints(norm)
        return {
            "fingerprint": assessment_fp,
            "assessment_date": info["assessment_date"],
            "hypothetical": info["hypothetical"],
            "date_rule": info["date_rule"],
            "mode": "vehicle" if case.get("mode") == "vehicle" else "walking",
            "active_projects": active,
            "inactive_projects": [describe(p) for p in info["inactive_projects"]],
            "closed_link_ids": closed,
            "journeys": rows,
            "custom_journey": custom_view,
        }

    def assess(self, payload):
        return self.assess_normalized(self.normalize(payload))

    def compare(self, payload):
        norm = self.normalize(payload, need_question=True)
        if norm["case"].get("mode") == "vehicle":
            raise ValueError("AI mitigation comparison is available only for walking")
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
