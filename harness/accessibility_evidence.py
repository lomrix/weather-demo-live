"""Summarize sourced accessibility evidence for the Koigen saved routes."""

import json
from pathlib import Path


EVIDENCE_FILE = "koigen-route-osm-evidence.json"
SURFACE_TAG = "surface"
SLOPE_TAG = "incline"


def load_evidence(root):
    path = Path(root) / "fixtures" / "accessibility" / EVIDENCE_FILE
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence["requirement"] != "avoid_steps":
        raise ValueError("Koigen accessibility evidence must use avoid_steps")
    if evidence["fixture"]["sanitized_fixture_sha256"] != (
        "1330a404409182d25111f767e1af2e4f484576dee0bce68b539c43467a74deca"
    ):
        raise ValueError("Koigen accessibility evidence is tied to a different map fixture")
    if evidence["route_node_elements"]["checked_count"] != len(
        evidence["route_node_elements"]["node_ids"]
    ):
        raise ValueError("Koigen route-node evidence count is inconsistent")
    return evidence


def _way_step_status(tags):
    if tags.get("highway") == "steps" or tags.get("step_count") not in (None, "0"):
        return "known_steps"
    if tags.get("step_count") == "0" or tags.get("steps") == "no":
        return "supported_step_free"
    return "unknown"


def _route_summary(case, evidence, path):
    links = []
    totals = {"known_steps": 0, "supported_step_free": 0, "unknown": 0}
    surfaces = {}
    slopes = {}
    between = {tuple(sorted((link["from"], link["to"]))): link for link in case["links"].values()}
    for start, end in zip(path, path[1:]):
        link = between[tuple(sorted((start, end)))]
        way_id = link["source"].rsplit("/", 1)[-1]
        source = evidence["way_elements"].get(way_id)
        if source is None:
            raise ValueError(f"Missing accessibility source evidence for OSM way {way_id}")
        tags = source["tags"]
        step_status = _way_step_status(tags)
        totals[step_status] += link["metres"]
        surface = tags.get(SURFACE_TAG, "unknown")
        slope = tags.get(SLOPE_TAG, "unknown")
        surfaces[surface] = surfaces.get(surface, 0) + link["metres"]
        slopes[slope] = slopes.get(slope, 0) + link["metres"]
        links.append({
            "link_id": link["id"],
            "way_id": way_id,
            "metres": link["metres"],
            "step_status": step_status,
            "surface": surface,
            "slope": slope,
            "source_url": source["source_url"],
            "source_version": source["version"],
            "source_timestamp": source["timestamp"],
        })
    return {
        "metres": sum(link["metres"] for link in links),
        "link_count": len(links),
        "step_status_metres": totals,
        "surface_metres": dict(sorted(surfaces.items())),
        "slope_metres": dict(sorted(slopes.items())),
        "links": links,
    }


def summarize(case, evidence, journey):
    baseline = _route_summary(case, evidence, journey["baseline_path"])
    detour = _route_summary(case, evidence, journey["path"])
    baseline_unknown = baseline["step_status_metres"]["unknown"]
    detour_unknown = detour["step_status_metres"]["unknown"]
    expected = evidence["route_way_metres"]
    for name, route in (("baseline", baseline), ("detour", detour)):
        actual = {}
        for link in route["links"]:
            actual[link["way_id"]] = actual.get(link["way_id"], 0) + link["metres"]
        if actual != expected[name]:
            raise ValueError(f"Koigen {name} route no longer matches saved accessibility evidence")
    return {
        "requirement": "Avoid steps",
        "shortest_route_metres": baseline["metres"],
        "modeled_detour_metres": detour["metres"],
        "alternative": {
            "status": "not_supported_by_evidence",
            "metres": None,
            "reason": (
                "No route can be identified as step-free: "
                f"{baseline_unknown} m of baseline links and {detour_unknown} m "
                "of modeled-detour links have unknown step status."
            ),
        },
        "baseline": baseline,
        "modeled_detour": detour,
        "provenance": {
            "snapshot_file": evidence["fixture"]["file"],
            "snapshot_retrieved_at": evidence["fixture"]["retrieved_at"],
            "snapshot_sha256": evidence["fixture"]["sanitized_fixture_sha256"],
            "evidence_checked_at": evidence["checked_at"],
            "source_method": evidence["source_method"],
            "attribution": evidence["fixture"]["attribution"],
            "license": evidence["fixture"]["license"],
            "route_nodes_checked": evidence["route_node_elements"]["checked_count"],
            "route_node_source_url_template": evidence["route_node_elements"]["source_url_template"],
        },
        "gaps": evidence["interpretation_limits"],
    }
