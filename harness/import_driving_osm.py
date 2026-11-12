"""Import a sanitized OSM road fixture into a conservative directed car graph."""

import xml.etree.ElementTree as ET

try:
    from .import_hamar_osm import _metres
    from .sanitize_driving_fixture import ROAD_TYPES
except ImportError:
    from import_hamar_osm import _metres
    from sanitize_driving_fixture import ROAD_TYPES


ACCESS_KEYS = ("motorcar", "motor_vehicle", "vehicle", "access")
ALLOWED_ACCESS = {"yes", "permissive", "designated", "official"}


def _tags(element):
    return {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}


def _allowed(tags):
    if any(key.endswith(":conditional") or
           any(key.startswith(base + ":") for base in ACCESS_KEYS)
           for key in tags if key != "highway"):
        return False
    for key in ACCESS_KEYS:
        if key in tags:
            return tags[key] in ALLOWED_ACCESS
    return True


def _direction(tags):
    for key in ("oneway:motorcar", "oneway:motor_vehicle", "oneway:vehicle", "oneway"):
        if key in tags:
            value = tags[key]
            if value in ("yes", "1", "true"):
                return "forward"
            if value in ("-1", "reverse"):
                return "reverse"
            if value in ("no", "0", "false"):
                return "both"
            return None
    if tags.get("junction") == "roundabout" or tags.get("highway") in {"motorway", "motorway_link"}:
        return "forward"
    return "both"


def import_roads(path):
    root = ET.parse(path).getroot()
    bounds = root.find("bounds")
    if root.tag != "osm" or bounds is None:
        raise ValueError("Road fixture needs OSM bounds")
    all_nodes = {node.attrib["id"]: node for node in root.findall("node")}
    coordinates = {key: (float(node.attrib["lat"]), float(node.attrib["lon"]))
                   for key, node in all_nodes.items()}
    blocked = set()
    for key, node in all_nodes.items():
        tags = _tags(node)
        if (tags.get("barrier") not in (None, "no") or not _allowed(tags)):
            blocked.add(key)
    links = []
    for way in root.findall("way"):
        tags = _tags(way)
        direction = _direction(tags)
        if tags.get("highway") not in ROAD_TYPES or not _allowed(tags) or direction is None:
            continue
        refs = [node.attrib["ref"] for node in way.findall("nd")]
        if any(ref not in coordinates for ref in refs):
            raise ValueError(f"Road way {way.attrib['id']} references a missing node")
        for index, (start, end) in enumerate(zip(refs, refs[1:]), 1):
            if start in blocked or end in blocked or start == end:
                continue
            length = _metres(coordinates[start], coordinates[end])
            if length <= 0:
                continue
            if direction == "reverse":
                start, end = end, start
            links.append({
                "id": f"osm-road-{way.attrib['id']}-segment-{index}",
                "from": start, "to": end, "metres": length, "modes": ["vehicle"],
                "oneway": direction != "both",
                "source": f"https://www.openstreetmap.org/way/{way.attrib['id']}",
            })
    used = {node for link in links for node in (link["from"], link["to"])}
    return {
        "nodes": {key: list(coordinates[key]) for key in used},
        "network": links,
        "bounds": {key: float(bounds.attrib[key]) for key in ("minlat", "minlon", "maxlat", "maxlon")},
    }
