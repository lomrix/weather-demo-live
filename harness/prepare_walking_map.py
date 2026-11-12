"""Download a rectangular OSM map in tiles and prepare a sanitized walking fixture."""

import argparse
import hashlib
import json
import math
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

try:
    from .merge_osm_tiles import merge
    from .sanitize_osm_fixture import sanitize
except ImportError:
    from merge_osm_tiles import merge
    from sanitize_osm_fixture import sanitize


def prepare(bounds, columns, rows, output, opener=urlopen, sanitizer=sanitize):
    if not all(math.isfinite(value) for value in bounds):
        raise ValueError("Bounds must be finite")
    west, south, east, north = (round(value, 7) for value in bounds)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Bounds must be valid west, south, east, north coordinates")
    if columns < 1 or rows < 1:
        raise ValueError("Rows and columns must be positive")
    if (east - west) * (north - south) / (columns * rows) > 0.25:
        raise ValueError("Each tile must be at most 0.25 square degrees")

    tiles = {}
    with tempfile.TemporaryDirectory(prefix="walking-map-") as directory:
        tmp = Path(directory)
        paths = []
        for row in range(rows):
            for col in range(columns):
                tile = (
                    west + (east - west) * col / columns,
                    south + (north - south) * row / rows,
                    west + (east - west) * (col + 1) / columns,
                    south + (north - south) * (row + 1) / rows,
                )
                if round(tile[0], 7) == round(tile[2], 7) or round(tile[1], 7) == round(tile[3], 7):
                    raise ValueError("Tile dimensions are too small for seven-decimal coordinates")
                bbox = ",".join(f"{value:.7f}" for value in tile)
                url = f"https://api.openstreetmap.org/api/0.6/map?bbox={bbox}"
                request = Request(url, headers={"User-Agent": "HamarAccessLab/1.0 (walking map preparation)"})
                with opener(request, timeout=120) as response:
                    raw = response.read()
                root = ET.fromstring(raw)
                element = root.find("bounds")
                if root.tag != "osm" or element is None:
                    raise ValueError(f"Invalid OSM tile response: {url}")
                actual = tuple(float(element.attrib[key]) for key in ("minlon", "minlat", "maxlon", "maxlat"))
                if any(abs(a - b) > 0.0000001 for a, b in zip(actual, tile)):
                    raise ValueError(f"Unexpected OSM tile bounds: {url}")
                name = f"tile-{row:03d}-{col:03d}.osm"
                path = tmp / name
                path.write_bytes(raw)
                paths.append(path)
                tiles[name] = {
                    "source_url": url,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
                print(f"Downloaded {name}", flush=True)
        merged = tmp / "merged.osm"
        merge_info = merge(paths, merged)
        sanitized = tmp / "sanitized.osm"
        info = sanitizer(merged, sanitized)
        root = ET.parse(sanitized).getroot()
        node_ids = {node.attrib["id"] for node in root.findall("node")}
        missing = {node.attrib["ref"] for node in root.findall("way/nd")} - node_ids
        if missing:
            raise ValueError(f"Retained ways reference {len(missing)} missing nodes")
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sanitized, output)
    return {
        "source_url": "https://api.openstreetmap.org/api/0.6/map (tiled bounding box)",
        "source_tiles": tiles,
        "retrieved_at": tiles[paths[-1].name]["retrieved_at"],
        "bounds": {"minlat": south, "minlon": west, "maxlat": north, "maxlon": east},
        "merge_procedure": "harness/merge_osm_tiles.py",
        "original_download_sha256": merge_info["merged_sha256"],
        "sanitized_fixture_sha256": info["sanitized_sha256"],
        "merged_node_count_before_sanitizing": merge_info["merged_node_count"],
        "merged_way_count_before_sanitizing": merge_info["merged_way_count"],
        "retained_way_count": info["retained_way_count"],
        "retained_node_count": info["retained_node_count"],
        "removed_contact_tag_keys": info["removed_contact_tag_keys"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bounds", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"), required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True,
                        help="Write the manifest entry as JSON at this path")
    args = parser.parse_args()
    if args.output.resolve() == args.metadata.resolve():
        parser.error("Output and metadata paths must differ")
    entry = prepare(args.bounds, args.columns, args.rows, args.output)
    args.metadata.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output} and {args.metadata}")


if __name__ == "__main__":
    main()
