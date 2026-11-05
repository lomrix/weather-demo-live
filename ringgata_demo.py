"""Replay the checked Ringgata notice and compare two illustrative routes."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE / "fixtures" / "ringgata-demo" / "ringgata.json"
BUS_FIXTURE = HERE / "fixtures" / "hamar-route-coverage-2026-10-21.json"
SNAPSHOT = HERE / "fixtures" / "ringgata-demo" / "input-snapshot.json"
RUN = HERE / "fixtures" / "ringgata-demo" / "run.json"
SOURCE = (
    "https://www.hamar.kommune.no/lokaldemokrati/"
    "oppstart-reguleringsplan-fv-187-ringgata-i-hamar"
)

sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE / "harness"))
from ringgata_checks import check
from route_coverage_report import analyse
from scenario_compare import shortest_route


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run(case_path, bus_path):
    case = read_json(case_path)
    snapshot = read_json(SNAPSHOT)
    model_response = read_json(RUN)["raw_model_response"]["response"]
    facts = json.loads(model_response)
    meta = snapshot["source_metadata"]
    errors, warnings = check(facts, snapshot["input_text"], meta)
    if errors or warnings:
        raise ValueError("Notice needs review: " + "; ".join(errors + warnings))
    if (
        facts["in_scope"] is not True
        or meta["source_url"] != SOURCE
        or facts["location"]["value"] != case["notice_location"]
    ):
        raise ValueError("The saved notice does not match this scenario location")

    edges = [{**edge, "modes": edge.get("modes", ["walking"])} for edge in case["edges"]]
    edge_ids = {edge["id"] for edge in edges}
    if len(edge_ids) != len(edges) or case["closure_edge"] not in edge_ids:
        raise ValueError("Edge IDs must be unique and the closure must name an existing edge")
    if any(type(edge["metres"]) is not int or edge["metres"] <= 0 for edge in edges):
        raise ValueError("Each edge must have a positive whole number of metres")
    endpoints = {edge[key] for edge in edges for key in ("from", "to")}
    if case["origin"] not in endpoints or case["destination"] not in endpoints:
        raise ValueError("The journey must start and end at known nodes")

    bus_bytes = bus_path.read_bytes()
    coverage = analyse(json.loads(bus_bytes), hashlib.sha256(bus_bytes).hexdigest())
    baseline = shortest_route(edges, case["origin"], case["destination"])
    if baseline["metres"] is None:
        raise ValueError("The baseline journey has no route")
    closure = shortest_route(
        edges, case["origin"], case["destination"], {case["closure_edge"]}
    )
    change = None if closure["metres"] is None else (
        closure["metres"] - baseline["metres"]
    )
    return {
        "mode": "offline_replay",
        "notice": {
            "source_url": SOURCE,
            "proposal": facts["proposal"],
            "location": facts["location"],
            "planning_stage": facts["planning_stage"],
        },
        "comparison": {
            "geometry": "illustrative",
            "closure": "hypothetical",
            "baseline": baseline,
            "crossing_closed": closure,
            "extra_metres": change,
        },
        "transport_context": {
            "relation_to_ringgata": "unverified",
            "source": coverage["source"],
            "service_dates": coverage["service_dates"],
            "routes": [route["published_name"] for route in coverage["routes"]],
            "totals": coverage["totals"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=CASE)
    parser.add_argument("--bus", type=Path, default=BUS_FIXTURE)
    parser.add_argument("--json", action="store_true", help="Print evidence and results as JSON")
    args = parser.parse_args()
    try:
        result = run(args.case, args.bus)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Demo stopped: {exc}\n")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return
    comparison = result["comparison"]
    bus = result["transport_context"]
    print("Ringgata | saved notice replay")
    print(f"Proposal: {result['notice']['proposal']['value']}")
    print("Illustrative walking links and distances. Closure is hypothetical.")
    if comparison["baseline"]["metres"] is None:
        print("Baseline: No route available")
    else:
        print(f"Baseline: {comparison['baseline']['metres']} m")
    if comparison["crossing_closed"]["metres"] is None:
        print("Crossing closed: No route available")
    else:
        print(f"Crossing closed: {comparison['crossing_closed']['metres']} m "
              f"({comparison['extra_metres']:+} m)")
    print(f"Saved Entur context ({', '.join(bus['service_dates'])}): "
          f"{bus['totals']['calls']} stop calls, {bus['totals']['actual']} actual, "
          f"{bus['totals']['prediction_only']} prediction-only")
    print("Connection between these bus observations and Ringgata: unverified.")


if __name__ == "__main__":
    main()
