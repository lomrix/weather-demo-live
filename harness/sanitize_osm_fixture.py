"""Create a contributor-metadata-free, walking-only OSM XML fixture."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path


WALKING_HIGHWAYS = {"footway", "path", "pedestrian", "cycleway"}
WALKING_TAGS = {"highway", "foot"}
CONTACT_TAGS = {"email", "fax", "mobile", "phone", "website"}
REMOVED_ATTRIBUTES = {"changeset", "timestamp", "uid", "user", "version"}


def _is_walking_way(tags):
    return tags.get("foot") != "no" and (
        tags.get("highway") in WALKING_HIGHWAYS
        or tags.get("foot") in {"yes", "designated"}
    )


def sanitize(input_path, output_path):
    root = ET.parse(input_path).getroot()
    retained_ways = []
    retained_node_ids = set()
    removed_contact_keys = set()
    removed_attribute_names = set()
    removed_way_count = 0
    removed_tag_count = 0

    for element in root.iter():
        if element is root:
            continue
        removed_attribute_names.update(
            name for name in element.attrib if name in REMOVED_ATTRIBUTES
        )
        for tag in element.findall("tag"):
            key = tag.attrib["k"]
            if key not in WALKING_TAGS:
                removed_tag_count += 1
                if key in CONTACT_TAGS or key.startswith("contact:") or "phone" in key:
                    removed_contact_keys.add(key)

    for way in root.findall("way"):
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        if not _is_walking_way(tags):
            removed_way_count += 1
            continue
        refs = [node.attrib["ref"] for node in way.findall("nd")]
        retained_node_ids.update(refs)
        retained_ways.append((way, refs))

    output_root = ET.Element("osm", root.attrib)
    for child in root:
        if child.tag == "bounds":
            output_root.append(ET.fromstring(ET.tostring(child, encoding="unicode")))
            break

    for node in sorted(root.findall("node"), key=lambda item: int(item.attrib["id"])):
        if node.attrib["id"] not in retained_node_ids:
            continue
        output_node = ET.Element("node", {
            key: node.attrib[key] for key in ("id", "lat", "lon")
        })
        output_root.append(output_node)

    for way, refs in sorted(retained_ways, key=lambda item: int(item[0].attrib["id"])):
        output_way = ET.SubElement(output_root, "way", {"id": way.attrib["id"]})
        for ref in refs:
            ET.SubElement(output_way, "nd", {"ref": ref})
        for tag in sorted(
            [tag for tag in way.findall("tag") if tag.attrib["k"] in WALKING_TAGS],
            key=lambda item: {"highway": 0, "foot": 1}[item.attrib["k"]],
        ):
            ET.SubElement(output_way, "tag", {
                "k": tag.attrib["k"],
                "v": tag.attrib["v"],
            })

    ET.indent(output_root, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(output_root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    output_path.write_bytes(output_path.read_bytes().replace(b"\r\n", b"\n"))
    return {
        "original_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "sanitized_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "retained_way_count": len(retained_ways),
        "retained_node_count": len(retained_node_ids),
        "removed_way_count": removed_way_count,
        "removed_tag_count": removed_tag_count,
        "removed_contact_tag_keys": sorted(removed_contact_keys),
        "removed_attributes": sorted(removed_attribute_names),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(sanitize(args.input, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
