"""Offline assessment of named construction projects active on a given date.

A scenario may carry a "projects" list. Each project has an id, label,
hypothetical (boolean), start_date, end_date (ISO YYYY-MM-DD, both inclusive) and explicit
"restrictions" using the existing close_links / restrict_links operations.
All projects active on the assessment date are applied together.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    from harness.scenario_compare import (
        _validate_journeys, _validate_network, shortest_route,
    )
except ImportError:
    from scenario_compare import _validate_journeys, _validate_network, shortest_route

DATE_RULE = (
    "Dates are ISO YYYY-MM-DD and both boundaries are inclusive: a project is "
    "active when start_date <= assessment date <= end_date."
)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_OPERATIONS = {"close_links": "walking", "restrict_links": "vehicle"}


def parse_date(value, label):
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be a date written as YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} is not a real calendar date: {value}") from None


def _validate_projects(projects, link_ids):
    if not isinstance(projects, list) or not projects:
        raise ValueError("scenario needs a non-empty projects list")
    parsed = []
    seen = set()
    for project in projects:
        if not isinstance(project, dict):
            raise ValueError("each project must be an object")
        project_id = project.get("id")
        if not isinstance(project_id, str) or not project_id.strip() or project_id in seen:
            raise ValueError("project IDs must be unique, non-empty strings")
        seen.add(project_id)
        label = project.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"project {project_id}: label must be a non-empty string")
        if type(project.get("hypothetical")) is not bool:
            raise ValueError(f"project {project_id}: hypothetical must be true or false")
        start = parse_date(project.get("start_date"), f"project {project_id}: start_date")
        end = parse_date(project.get("end_date"), f"project {project_id}: end_date")
        if end < start:
            raise ValueError(
                f"project {project_id}: end_date {end} is before start_date {start}"
            )
        restrictions = project.get("restrictions")
        if not isinstance(restrictions, list) or not restrictions:
            raise ValueError(f"project {project_id}: restrictions are required")
        closed = set()
        restricted = set()
        for restriction in restrictions:
            if not isinstance(restriction, dict):
                raise ValueError(f"project {project_id}: restriction must be an object")
            kind = restriction.get("type")
            if kind not in _OPERATIONS:
                raise ValueError(f"project {project_id}: unknown restriction type {kind}")
            if restriction.get("mode") != _OPERATIONS[kind]:
                raise ValueError(
                    f"project {project_id}: {kind} requires {_OPERATIONS[kind]} mode"
                )
            listed = restriction.get("link_ids")
            if not isinstance(listed, list) or not listed:
                raise ValueError(f"project {project_id}: link_ids are required")
            for link_id in listed:
                if link_id not in link_ids:
                    raise ValueError(f"project {project_id}: unknown link ID {link_id}")
                if link_id in closed or link_id in restricted:
                    raise ValueError(
                        f"project {project_id}: ambiguous repeated link {link_id}"
                    )
                (closed if kind == "close_links" else restricted).add(link_id)
        parsed.append({
            "id": project_id, "label": label, "hypothetical": project["hypothetical"], "start": start, "end": end,
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "closed_walking_links": sorted(closed),
            "restricted_vehicle_links": sorted(restricted),
        })
    return parsed


def _worse_key(metres):
    return float("inf") if metres is None else metres


def assess_projects(scenario, assessment_date):
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be an object")
    network = scenario.get("network")
    link_ids, endpoints = _validate_network(network)
    journeys = scenario.get("journeys")
    _validate_journeys(journeys, endpoints)
    projects = _validate_projects(scenario.get("projects"), link_ids)
    when = parse_date(assessment_date, "assessment date")
    mode = scenario.get("routing_mode", "walking")
    if mode not in ("walking", "vehicle"):
        raise ValueError("routing_mode must be walking or vehicle")

    active = [p for p in projects if p["start"] <= when <= p["end"]]
    inactive = [p for p in projects if p not in active]

    def metres(origin, destination, chosen):
        key = "closed_walking_links" if mode == "walking" else "restricted_vehicle_links"
        closed = {link for p in chosen for link in p[key]}
        if mode == "walking":
            return shortest_route(network, origin, destination, closed)
        return shortest_route(network, origin, destination, closed, mode="vehicle")

    baseline_rows, rows = [], []
    for journey in journeys:
        origin, destination = journey["origin"], journey["destination"]
        baseline = metres(origin, destination, [])
        if baseline["metres"] is None:
            raise ValueError(f"journey {journey['id']}: baseline destination is unreachable")
        baseline_rows.append({"journey_id": journey["id"], "route": baseline})
        combined = metres(origin, destination, active)
        individual = {}
        for project in active:
            alone = metres(origin, destination, [project])["metres"]
            individual[project["id"]] = {
                "metres": alone,
                "change_metres": None if alone is None else alone - baseline["metres"],
            }
        contributors = []
        for project in active:
            without = metres(origin, destination, [p for p in active if p is not project])
            if (
                individual[project["id"]]["metres"] != baseline["metres"]
                or without["metres"] != combined["metres"]
            ):
                contributors.append(project["id"])
        change = None if combined["metres"] is None else combined["metres"] - baseline["metres"]
        overlap_effect = len(active) > 1 and bool(individual) and _worse_key(
            combined["metres"]
        ) > max(_worse_key(item["metres"]) for item in individual.values())
        rows.append({
            "journey_id": journey["id"],
            "baseline": baseline,
            "route": combined,
            "change_metres": change,
            "status": (
                "unreachable" if combined["metres"] is None
                else "longer" if change else "unchanged"
            ),
            "contributing_projects": contributors,
            "individual_projects": individual,
            "overlap_effect": overlap_effect,
        })

    def describe(project):
        return {key: project[key] for key in (
            "id", "label", "hypothetical", "start_date", "end_date",
            "closed_walking_links", "restricted_vehicle_links",
        )}

    metadata = dict(scenario.get("metadata", {}))
    names = ", ".join(p["id"] for p in active) or "none"
    hypothetical = any(p["hypothetical"] for p in active)
    return {
        "mode": "offline_project_assessment",
        "comparison": {
            "scenario": metadata,
            "baseline": baseline_rows,
            "alternatives": [{
                "id": "active-projects",
                "label": f"All active projects on {when.isoformat()} ({names})",
                "hypothetical": hypothetical,
                "journeys": rows,
            }],
        },
        "project_assessment": {
            "assessment_date": when.isoformat(),
            "hypothetical": hypothetical,
            "date_rule": DATE_RULE,
            "active_projects": [describe(p) for p in active],
            "inactive_projects": [describe(p) for p in inactive],
        },
    }


def format_text(result):
    info = result["project_assessment"]
    lines = [f"Assessment date: {info['assessment_date']}", info["date_rule"]]
    if info["hypothetical"]:
        lines.append("HYPOTHETICAL: at least one active project is hypothetical.")
    active = ", ".join(p["id"] for p in info["active_projects"]) or "none"
    lines.append(f"Active projects: {active}")
    for row in result["comparison"]["alternatives"][0]["journeys"]:
        base = row["baseline"]["metres"]
        if row["route"]["metres"] is None:
            outcome = "no route available"
        else:
            outcome = f"{row['route']['metres']} m ({row['change_metres']:+} m)"
        lines.append(
            f"  {row['journey_id']}: baseline {base} m, combined {outcome}; "
            f"contributing: {', '.join(row['contributing_projects']) or 'none'}"
            + ("; overlap worsens result" if row["overlap_effect"] else "")
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--date", required=True, help="Assessment date, YYYY-MM-DD")
    parser.add_argument("--json", action="store_true", help="Print checked JSON")
    args = parser.parse_args()
    try:
        scenario = json.loads(args.scenario.read_text(encoding="utf-8-sig"))
        result = assess_projects(scenario, args.date)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Project assessment stopped: {exc}\n")
    print(json.dumps(result, indent=2) if args.json else format_text(result))


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
