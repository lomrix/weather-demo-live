"""Build the Hamar walking scenario from a local OSM XML extract."""

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path


WALKING_HIGHWAYS = {"footway", "path", "pedestrian", "cycleway"}
WALKING_TAGS = {
    "highway": sorted(WALKING_HIGHWAYS),
    "foot": ["yes", "designated"],
    "excluded": {"foot": ["no"]},
}


def _metres(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    scale = math.cos(math.radians((lat1 + lat2) / 2))
    return int(round(math.hypot((lat2 - lat1) * 111320, (lon2 - lon1) * 111320 * scale)))


def _geometry_metres(a, b):
    lat1, lon1 = a
    lat2, lon2 = b
    scale = math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(
        (lat2 - lat1) * 111320,
        (lon2 - lon1) * 111320 * scale,
    )


def _is_walking_way(tags):
    if tags.get("foot") == "no":
        return False
    return (
        tags.get("highway") in WALKING_HIGHWAYS
        or tags.get("foot") in {"yes", "designated"}
    )


def import_scenario(source_path, template_path):
    template = json.loads(template_path.read_text(encoding="utf-8"))
    import_config = template["osm_import"]
    journeys_config = import_config["journeys"]
    closure = import_config["closure"]
    raw = source_path.read_bytes()
    root = ET.fromstring(raw)
    nodes = {
        node.attrib["id"]: (float(node.attrib["lat"]), float(node.attrib["lon"]))
        for node in root.findall("node")
    }
    network = []
    walking_way_ids = []
    interrupted_ids = []
    section_metres = 0.0
    interrupted_refs = None
    for way in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        if not _is_walking_way(tags):
            continue
        refs = [
            node.attrib["ref"]
            for node in way.findall("nd")
            if node.attrib["ref"] in nodes
        ]
        if len(refs) < 2:
            continue
        way_id = way.attrib["id"]
        walking_way_ids.append(way_id)
        if way_id == closure["way_id"]:
            interrupted_refs = refs
        for index, (start, end) in enumerate(zip(refs, refs[1:]), 1):
            metres = _metres(nodes[start], nodes[end])
            if metres <= 0:
                continue
            link_id = f"osm-way-{way_id}-segment-{index}"
            network.append({
                "id": link_id,
                "from": start,
                "to": end,
                "metres": metres,
                "modes": ["walking"],
                "source": f"https://www.openstreetmap.org/way/{way_id}",
            })
            if (
                way_id == closure["way_id"]
                and closure["from"] in refs
                and closure["to"] in refs
                and refs.index(closure["from"]) <= index - 1 < refs.index(closure["to"])
            ):
                interrupted_ids.append(link_id)
                section_metres += _geometry_metres(nodes[start], nodes[end])
    if interrupted_refs is None:
        raise ValueError(f"interrupted way {closure['way_id']} is missing")
    if not interrupted_ids:
        raise ValueError("interrupted endpoint section is missing")
    metadata = template["metadata"]
    extract = metadata["map_extract"]
    extract["downloaded_input"] = {
        "path": str(source_path),
        "retrieved_at": "2026-11-04T16:59:21+01:00",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bounds": root.find("bounds").attrib if root.find("bounds") is not None else None,
    }
    for journey in journeys_config:
        extract.setdefault("journeys", {})[journey["id"]] = {
            "origin": {
                "node_id": journey["origin"],
                "coordinates": list(nodes[journey["origin"]]),
            },
            "destination": {
                "node_id": journey["destination"],
                "coordinates": list(nodes[journey["destination"]]),
            },
        }
    first_journey = journeys_config[0]
    extract["origin"] = extract["journeys"][first_journey["id"]]["origin"]
    extract["destination"] = extract["journeys"][first_journey["id"]]["destination"]
    extract["interrupted_link"]["coordinates"] = {
        "from": list(nodes[closure["from"]]),
        "to": list(nodes[closure["to"]]),
    }
    extract["interrupted_link"]["section_metres_geometry"] = round(section_metres, 1)
    extract["interrupted_link"]["closure_segment_ids"] = interrupted_ids
    extract["walking_tag_policy"] = WALKING_TAGS
    extract["walking_way_count"] = len(set(walking_way_ids))
    extract["source_note"] = (
        "Graph includes ways tagged highway=footway, path, pedestrian or cycleway, "
        "and ways tagged foot=yes or foot=designated; foot=no overrides these "
        "defaults. Other highway types are excluded."
    )
    extract.pop("alternative_finding", None)
    extract.pop("downloaded_baseline_metres", None)
    extract.pop("downloaded_detour_metres", None)
    extract.pop("downloaded_detour_change_metres", None)
    used_node_ids = {
        node_id
        for link in network
        for node_id in (link["from"], link["to"])
    }
    extract["route_map"] = {
        "attribution": "© OpenStreetMap contributors",
        "detour_alternative_id": "hypothetical-pedestrian-interruption",
        "node_coordinates": {
            node_id: list(coordinates)
            for node_id, coordinates in nodes.items()
            if node_id in used_node_ids
        },
        "context_links": [
            {
                "id": link["id"],
                "from": link["from"],
                "to": link["to"],
            }
            for link in network
            if "walking" in link["modes"]
        ],
        "candidate_links": [
            {
                **candidate,
                "geometry": [
                    list(nodes[candidate["from"]]),
                    list(nodes[candidate["to"]]),
                ],
            }
            for candidate in import_config["candidates"]
        ],
    }
    vehicle_links = [
        link for link in template["network"] if link["modes"] == ["vehicle"]
    ]
    network.extend(vehicle_links)
    scenario = {
        "metadata": metadata,
        "network": network,
        "journeys": [
            {
                **journey,
                "evidence": next(
                    item["evidence"]
                    for item in template["journeys"]
                    if item["id"] == journey["id"]
                ),
            }
            for journey in journeys_config
        ],
        "candidates": [
            {
                **candidate,
                "geometry": [
                    list(nodes[candidate["from"]]),
                    list(nodes[candidate["to"]]),
                ],
            }
            for candidate in import_config["candidates"]
        ],
        "alternatives": [
            {
                "id": "vehicle-only-restriction",
                "label": "Vehicle-only restriction (modeled)",
                "operations": [{
                    "type": "restrict_links",
                    "mode": "vehicle",
                    "link_ids": [link["id"] for link in vehicle_links],
                }],
            },
            {
                "id": "hypothetical-pedestrian-interruption",
                "label": "Hypothetical pedestrian interruption",
                "hypothetical": True,
                "operations": [{
                    "type": "close_links",
                    "mode": "walking",
                    "link_ids": interrupted_ids,
                }],
            },
        ],
    }
    return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenario = import_scenario(args.input, args.template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scenario, indent=2, ensure_ascii=True), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
