"""Merge adjacent OSM API map downloads into one OSM XML file for sanitizing.

The OSM API refuses bounding boxes with more than 50000 nodes, so a wider area
is downloaded as unedited tiles. Elements are de-duplicated by id and the
output bounds are the union of the tile bounds. No other content is changed.
"""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def merge(input_paths, output_path):
    roots = [ET.parse(path).getroot() for path in input_paths]
    bounds = []
    for root in roots:
        element = root.find("bounds")
        if element is None:
            raise ValueError("every tile needs a bounds element")
        bounds.append({key: float(element.attrib[key]) for key in ("minlat", "minlon", "maxlat", "maxlon")})

    merged = ET.Element("osm", roots[0].attrib)
    ET.SubElement(merged, "bounds", {
        "minlat": f"{min(item['minlat'] for item in bounds):.7f}",
        "minlon": f"{min(item['minlon'] for item in bounds):.7f}",
        "maxlat": f"{max(item['maxlat'] for item in bounds):.7f}",
        "maxlon": f"{max(item['maxlon'] for item in bounds):.7f}",
    })
    counts = {}
    for tag in ("node", "way"):
        seen = {}
        for root in roots:
            for element in root.findall(tag):
                seen.setdefault(element.attrib["id"], element)
        counts[tag] = len(seen)
        for key in sorted(seen, key=int):
            merged.append(seen[key])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(merged).write(output_path, encoding="utf-8", xml_declaration=True)
    return {
        "tile_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths},
        "merged_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "merged_node_count": counts["node"],
        "merged_way_count": counts["way"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge(args.input, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
