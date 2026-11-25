"""Capture or replay a Hamar municipal OSM source without replacing checked fixtures.

Live mode makes one opt-in request. Replay and normal app routing are offline.
The output directory must be new, so source revisions remain reviewable.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from .address_search import NoRedirect
from .municipal_walk import streets

ENDPOINT = "https://overpass-api.de/api/interpreter"
QUERY = '[out:json][timeout:60];area["boundary"="administrative"]["ref"="3403"]["admin_level"="7"]->.hamar;.hamar out tags;way["highway"](area.hamar);(._;>;);out body;'
MAX_BYTES = 32 * 1024 * 1024
TAGS = {"highway", "foot", "access", "motorroad", "name", "barrier", "sidewalk",
        "surface", "incline", "foot:conditional", "access:conditional", "oneway:foot"}


def project(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Municipal source exceeds 32 MiB")
    data = json.loads(raw)
    if data.get("remark"):
        raise ValueError("Municipal source reported an incomplete query")
    elements = data.get("elements", [])
    areas = [e for e in elements if e.get("type") == "area"]
    if len(areas) != 1 or areas[0].get("tags", {}).get("ref") != "3403":
        raise ValueError("Expected exactly one Hamar municipality area")
    clean = []
    for element in elements:
        kind = element.get("type")
        if kind not in {"way", "node"}:
            continue
        item = {"type": kind, "id": element["id"]}
        item.update({key: element[key] for key in ("lat", "lon", "nodes") if key in element})
        item["tags"] = {key: value for key, value in element.get("tags", {}).items() if key in TAGS}
        clean.append(item)
    node_ids = {e["id"] for e in clean if e["type"] == "node"}
    ways = [e for e in clean if e["type"] == "way"]
    if not ways or any(ref not in node_ids for way in ways for ref in way["nodes"]):
        raise ValueError("Municipal source has no ways or missing referenced nodes")
    return {"source_url": ENDPOINT, "query": QUERY,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source_timestamp": data.get("osm3s", {}).get("timestamp_osm_base"),
            "original_download_sha256": hashlib.sha256(raw).hexdigest(),
            "area": {"id": areas[0]["id"], "name": areas[0]["tags"].get("name"), "ref": "3403"},
            "attribution": "© OpenStreetMap contributors",
            "licence_url": "https://opendatacommons.org/licenses/odbl/1-0/", "elements": clean}


def prepare(output, source=None, live=False, opener=None):
    output = Path(output)
    if output.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    if (source is None) == (not live):
        raise ValueError("Choose either a saved source or explicit live acquisition")
    if live:
        request = Request(ENDPOINT, data=urlencode({"data": QUERY}).encode(), headers={
            "User-Agent": "HamarAccessLab/1.0 municipal-walking-import",
            "Content-Type": "application/x-www-form-urlencoded"})
        with (opener or build_opener(NoRedirect()).open)(request, timeout=75) as response:
            raw = response.read(MAX_BYTES + 1)
        data = project(raw)
        saved = (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    else:
        saved = Path(source).read_bytes()
        if len(saved) > MAX_BYTES:
            raise ValueError("Saved source exceeds 32 MiB")
        data = json.loads(saved)
        if data.get("area", {}).get("ref") != "3403":
            raise ValueError("Saved source is not for Hamar municipality")
    index = {"source_sha256": hashlib.sha256(saved).hexdigest(), "streets": streets(data)}
    output.mkdir(parents=True)
    (output / "hamar-municipality.json").write_bytes(saved)
    index_path = output / "hamar-municipality-streets.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    summary = {"source_url": data["source_url"], "query": data["query"],
               "retrieved_at": data["retrieved_at"], "source_timestamp": data["source_timestamp"],
               "original_download_sha256": data["original_download_sha256"],
               "sanitized_fixture_sha256": hashlib.sha256(saved).hexdigest(),
               "street_index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
               "source_way_count": sum(e["type"] == "way" for e in data["elements"]),
               "source_node_count": sum(e["type"] == "node" for e in data["elements"]),
               "named_street_count": len(index["streets"]), "live_request": live}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--live", action="store_true")
    modes.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.source, args.live), indent=2))


if __name__ == "__main__":
    main()
