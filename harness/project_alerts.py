"""Build source-backed in-app alerts for saved walking journeys."""

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

try:
    from .project_scenario import assess_projects, parse_date
except ImportError:
    from project_scenario import assess_projects, parse_date


CURRENT_FILE = "hamar-walking-projects-current.json"
BASE_FILE = "hamar-walking-projects-base.json"
MAX_SAVED_JOURNEYS = 20
APPROACHING_DAYS = 14


def load_snapshot(root, revision="current"):
    if revision not in {"current", "base"}:
        raise ValueError("Choose a listed saved project snapshot")
    filename = CURRENT_FILE if revision == "current" else BASE_FILE
    path = Path(root) / "fixtures" / "projects" / filename
    try:
        raw = path.read_bytes()
        snapshot = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Saved project data is unavailable: {filename}") from exc
    if (
        not isinstance(snapshot, dict)
        or not isinstance(snapshot.get("id"), str)
        or type(snapshot.get("synthetic")) is not bool
        or not isinstance(snapshot.get("source"), dict)
        or not isinstance(snapshot.get("projects"), list)
        or not snapshot["projects"]
    ):
        raise ValueError(f"Saved project data is invalid: {filename}")
    source = snapshot["source"]
    for key in ("label", "file", "kind", "retrieved_at", "attribution"):
        if not isinstance(source.get(key), str) or not source[key].strip():
            raise ValueError(f"Saved project source is missing {key}")
    ids = set()
    for project in snapshot["projects"]:
        required_text = (
            "id", "label", "start_date", "end_date",
            "source_url", "source_label",
        )
        if (
            not isinstance(project, dict)
            or any(not isinstance(project.get(key), str) or not project[key].strip()
                   for key in required_text)
            or project["id"] in ids
            or type(project.get("hypothetical")) is not bool
            or type(project.get("reopening_confirmed")) is not bool
            or not isinstance(project.get("section_ids"), list)
            or not project["section_ids"]
        ):
            raise ValueError(f"Saved project record is invalid in {filename}")
        ids.add(project["id"])
        start = parse_date(project["start_date"], f"{project['id']}: start_date")
        end = parse_date(project["end_date"], f"{project['id']}: end_date")
        if end < start:
            raise ValueError(f"Saved project date range is invalid: {project['id']}")
        if project["reopening_confirmed"] and not project.get("reopening_confirmed_at"):
            raise ValueError(f"Confirmed reopening lacks a source timestamp: {project['id']}")
    snapshot["sha256"] = hashlib.sha256(raw).hexdigest()
    return snapshot


def _valid_journey(journey):
    if not isinstance(journey, dict) or not isinstance(journey.get("id"), str):
        return False
    if not isinstance(journey.get("name"), str) or not journey["name"].strip():
        return False
    if not isinstance(journey.get("case_id"), str):
        return False
    for side in ("origin", "destination"):
        endpoint = journey.get(side)
        if not isinstance(endpoint, dict):
            return False
        coordinates = endpoint.get("coordinates")
        if (
            not isinstance(coordinates, list)
            or len(coordinates) != 2
            or any(type(value) not in (int, float) for value in coordinates)
        ):
            return False
    return True


def _fingerprint(project):
    return {
        key: project.get(key)
        for key in (
            "id", "label", "start_date", "end_date", "section_ids",
            "reopening_confirmed", "reopening_confirmed_at", "source_url",
            "source_label",
        )
    }


def _source(snapshot, project):
    source = snapshot["source"]
    return {
        "project_source_label": project["source_label"],
        "project_source_url": project["source_url"],
        "snapshot_source_label": source["label"],
        "snapshot_file": source["file"],
        "snapshot_sha256": snapshot["sha256"],
        "snapshot_retrieved_at": source["retrieved_at"],
        "attribution": source["attribution"],
    }


def build_alerts(workspace, root, saved_journeys, previous_projects, revision="current", as_of=None):
    if not isinstance(saved_journeys, list) or len(saved_journeys) > MAX_SAVED_JOURNEYS:
        raise ValueError(f"Send up to {MAX_SAVED_JOURNEYS} saved journeys")
    if not all(_valid_journey(journey) for journey in saved_journeys):
        raise ValueError("Saved journey data is invalid")
    if previous_projects is None:
        previous_projects = []
    if not isinstance(previous_projects, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str)
        for item in previous_projects
    ):
        raise ValueError("Previous project snapshot is invalid")
    snapshot = load_snapshot(root, revision)
    when = date.today() if as_of is None else parse_date(as_of, "alert assessment date")
    checked_at = datetime.now(timezone.utc).astimezone().isoformat()
    previous = {item["id"]: item for item in previous_projects}
    alerts = []
    unresolved = []
    for journey in saved_journeys:
        try:
            case = workspace.get_case(journey["case_id"])
            if case.get("mode") == "vehicle":
                raise ValueError("Saved alerts support walking journeys only")
            resolved = workspace.resolve_custom(case, {
                "origin": tuple(journey["origin"]["coordinates"]),
                "destination": tuple(journey["destination"]["coordinates"]),
            })
            if resolved["status"] != "ready":
                unresolved.append({
                    "journey_id": journey["id"],
                    "journey_name": journey["name"],
                    "kind": "journey_unavailable",
                    "message": resolved["message"],
                })
                continue
        except (LookupError, ValueError) as exc:
            unresolved.append({
                "journey_id": journey["id"],
                "journey_name": journey["name"],
                "kind": "journey_unavailable",
                "message": str(exc),
            })
            continue
        section_ids = case["section_ids"]
        for project in snapshot["projects"]:
            if any(section not in section_ids for section in project["section_ids"]):
                unresolved.append({
                    "journey_id": journey["id"],
                    "journey_name": journey["name"],
                    "kind": "project_unavailable",
                    "message": f"{project['id']}: a project section is not in the selected walking map",
                })
                continue
            start = date.fromisoformat(project["start_date"])
            end = date.fromisoformat(project["end_date"])
            relevant = False
            result = None
            if start <= when <= end:
                scenario = {
                    "metadata": {"id": snapshot["id"], "synthetic": snapshot["synthetic"]},
                    "network": case["scenario"]["network"],
                    "routing_mode": "walking",
                    "journeys": [{
                        "id": "saved",
                        "origin": resolved["origin"]["node_id"],
                        "destination": resolved["destination"]["node_id"],
                    }],
                    "projects": [{
                        "id": project["id"],
                        "label": project["label"],
                        "hypothetical": bool(project["hypothetical"]),
                        "start_date": project["start_date"],
                        "end_date": project["end_date"],
                        "restrictions": [{
                            "type": "close_links",
                            "mode": "walking",
                            "link_ids": [
                                link_id
                                for section in project["section_ids"]
                                for link_id in section_ids[section]["link_ids"]
                            ],
                        }],
                    }],
                }
                result = assess_projects(scenario, when.isoformat())[
                    "comparison"
                ]["alternatives"][0]["journeys"][0]
                relevant = result["status"] != "unchanged"
            elif start > when:
                preview = {
                    "metadata": {"id": snapshot["id"]},
                    "network": case["scenario"]["network"],
                    "routing_mode": "walking",
                    "journeys": [{
                        "id": "saved",
                        "origin": resolved["origin"]["node_id"],
                        "destination": resolved["destination"]["node_id"],
                    }],
                    "projects": [{
                        "id": project["id"],
                        "label": project["label"],
                        "hypothetical": bool(project["hypothetical"]),
                        "start_date": project["start_date"],
                        "end_date": project["end_date"],
                        "restrictions": [{
                            "type": "close_links",
                            "mode": "walking",
                            "link_ids": [
                                link_id
                                for section in project["section_ids"]
                                for link_id in section_ids[section]["link_ids"]
                            ],
                        }],
                    }],
                }
                result = assess_projects(preview, start.isoformat())[
                    "comparison"
                ]["alternatives"][0]["journeys"][0]
                relevant = result["status"] != "unchanged"
            else:
                preview = {
                    "metadata": {"id": snapshot["id"]},
                    "network": case["scenario"]["network"],
                    "routing_mode": "walking",
                    "journeys": [{
                        "id": "saved",
                        "origin": resolved["origin"]["node_id"],
                        "destination": resolved["destination"]["node_id"],
                    }],
                    "projects": [{
                        "id": project["id"],
                        "label": project["label"],
                        "hypothetical": bool(project["hypothetical"]),
                        "start_date": project["start_date"],
                        "end_date": project["end_date"],
                        "restrictions": [{
                            "type": "close_links",
                            "mode": "walking",
                            "link_ids": [
                                link_id
                                for section in project["section_ids"]
                                for link_id in section_ids[section]["link_ids"]
                            ],
                        }],
                    }],
                }
                result = assess_projects(preview, start.isoformat())[
                    "comparison"
                ]["alternatives"][0]["journeys"][0]
                relevant = result["status"] != "unchanged"

            def add(kind, suffix, message):
                stable = f"{journey['id']}:{project['id']}:{kind}:{suffix}"
                alert = {
                    "id": hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20],
                    "journey_id": journey["id"],
                    "journey_name": journey["name"],
                    "project_id": project["id"],
                    "project_label": project["label"],
                    "synthetic": bool(project["hypothetical"]),
                    "kind": kind,
                    "message": message,
                    "start_date": project["start_date"],
                    "end_date": project["end_date"],
                    "checked_at": checked_at,
                    "source": _source(snapshot, project),
                }
                if result is not None:
                    alert["route_effect"] = {
                        "status": result["status"],
                        "baseline_metres": result["baseline"]["metres"],
                        "metres": result["route"]["metres"],
                        "change_metres": result["change_metres"],
                    }
                alerts.append(alert)

            if relevant and 0 <= (start - when).days <= APPROACHING_DAYS:
                add(
                    "approaching_works",
                    project["start_date"],
                    f"Works start on {project['start_date']} and affect this saved journey.",
                )
            if relevant and start <= when <= end:
                effect = "make the route unreachable" if result["status"] == "unreachable" else (
                    f"change the route from {result['baseline']['metres']} m "
                    f"to {result['route']['metres']} m"
                )
                add(
                    "active_impact",
                    f"{project['start_date']}:{project['end_date']}:{result['status']}",
                    f"Active works {effect}.",
                )
            old = previous.get(project["id"])
            if relevant and old and (
                old.get("start_date"), old.get("end_date")
            ) != (project["start_date"], project["end_date"]):
                add(
                    "dates_changed",
                    f"{old.get('start_date')}:{old.get('end_date')}:{project['start_date']}:{project['end_date']}",
                    (
                        f"Project dates changed from {old.get('start_date')}–{old.get('end_date')} "
                        f"to {project['start_date']}–{project['end_date']}."
                    ),
                )
            if relevant and project.get("reopening_confirmed") is True:
                add(
                    "reopening_confirmed",
                    project.get("reopening_confirmed_at", project["end_date"]),
                    "The saved source explicitly confirms reopening.",
                )
            elif relevant and end < when:
                add(
                    "reopening_unconfirmed",
                    project["end_date"],
                    "Scheduled end passed; reopening unconfirmed.",
                )
    unique = {alert["id"]: alert for alert in alerts}
    return {
        "checked_at": checked_at,
        "as_of": when.isoformat(),
        "check_scope": "Checked when the app opened or the user requested a refresh; not continuous monitoring.",
        "snapshot": {
            "id": snapshot["id"],
            "sha256": snapshot["sha256"],
            "projects": [_fingerprint(project) for project in snapshot["projects"]],
            "source": snapshot["source"],
        },
        "alerts": list(unique.values()),
        "unavailable": unresolved,
    }
