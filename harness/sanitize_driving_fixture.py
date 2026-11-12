"""Create a contributor-metadata-free OSM road fixture for car routing."""

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


ROAD_TYPES = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "living_street", "service",
}
ROAD_TAGS = {
    "highway", "access", "vehicle", "motor_vehicle", "motorcar", "oneway",
    "oneway:vehicle", "oneway:motor_vehicle", "oneway:motorcar", "junction",
    "access:conditional", "vehicle:conditional", "motor_vehicle:conditional",
    "motorcar:conditional", "oneway:conditional", "oneway:vehicle:conditional", "oneway:motor_vehicle:conditional",
    "oneway:motorcar:conditional",
}
NODE_TAGS = {
    "barrier", "access", "vehicle", "motor_vehicle", "motorcar",
    "access:conditional", "vehicle:conditional", "motor_vehicle:conditional",
    "motorcar:conditional",
}
for key in ("access", "vehicle", "motor_vehicle", "motorcar"):
    for suffix in ("forward", "backward", "lanes"):
        ROAD_TAGS.add(f"{key}:{suffix}")
        ROAD_TAGS.add(f"{key}:{suffix}:conditional")


def sanitize(input_path, output_path):
    root = ET.parse(input_path).getroot()
    ways = []
    node_ids = set()
    removed_contact_keys = set()
    for tag in root.iter("tag"):
        key = tag.attrib["k"]
        if key in {"email", "fax", "mobile", "phone", "website"} or key.startswith("contact:") or "phone" in key:
            removed_contact_keys.add(key)
    for way in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        if tags.get("highway") not in ROAD_TYPES:
            continue
        ways.append(way)
        node_ids.update(nd.attrib["ref"] for nd in way.findall("nd"))
    result = ET.Element("osm", root.attrib)
    bounds = root.find("bounds")
    if bounds is None:
        raise ValueError("OSM input has no bounds")
    result.append(ET.fromstring(ET.tostring(bounds)))
    for node in sorted(root.findall("node"), key=lambda item: int(item.attrib["id"])):
        if node.attrib["id"] not in node_ids:
            continue
        out = ET.SubElement(result, "node", {key: node.attrib[key] for key in ("id", "lat", "lon")})
        for tag in sorted(node.findall("tag"), key=lambda item: item.attrib["k"]):
            if tag.attrib["k"] in NODE_TAGS:
                ET.SubElement(out, "tag", {"k": tag.attrib["k"], "v": tag.attrib["v"]})
    for way in sorted(ways, key=lambda item: int(item.attrib["id"])):
        out = ET.SubElement(result, "way", {"id": way.attrib["id"]})
        for nd in way.findall("nd"):
            ET.SubElement(out, "nd", {"ref": nd.attrib["ref"]})
        for tag in sorted(way.findall("tag"), key=lambda item: item.attrib["k"]):
            if tag.attrib["k"] in ROAD_TAGS:
                ET.SubElement(out, "tag", {"k": tag.attrib["k"], "v": tag.attrib["v"]})
    ET.indent(result, space="  ")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(result).write(output_path, encoding="utf-8", xml_declaration=True)
    output_path.write_bytes(output_path.read_bytes().replace(b"\r\n", b"\n"))
    return {
        "sanitized_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "retained_way_count": len(ways),
        "retained_node_count": len(node_ids),
        "removed_contact_tag_keys": sorted(removed_contact_keys),
    }
