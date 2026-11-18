"""Build the reproducible Hamar place index from saved local sources."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
from workspace_service import CASES, Workspace


BUS_FIXTURES = (
    ROOT / "fixtures" / "scenarios" / "hamar-b21-2026-11-12.json",
    ROOT / "fixtures" / "scenarios" / "hamar-b23-2026-11-12.json",
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path, **extra):
    return {
        "file": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(path),
        **extra,
    }


def build(root=ROOT):
    workspace = Workspace(root, load_places=False)
    places, seen_bus = [], set()
    sources = []
    for path in BUS_FIXTURES:
        bus = json.loads(path.read_text(encoding="utf-8"))
        source = _source(
            path,
            provider="Entur AS",
            attribution=bus["sources"]["attribution"],
            licence_url=bus["sources"]["licence_url"],
            service=bus["service"],
            service_date=bus["service_date"],
            retrieved_at_utc=bus["sources"]["retrieved_at_utc"],
            source_url=bus["sources"]["timetable_url"],
        )
        sources.append(source)
        for stop in bus["stops"]:
            entry_key = (stop["name"].casefold(), tuple(stop["coordinates"]))
            if entry_key in seen_bus:
                continue
            seen_bus.add(entry_key)
            places.append({
                "id": f"entur-{stop['id'].split(':')[-1]}-{len(places)}",
                "name": stop["name"],
                "kind": "bus_stop",
                "coordinates": stop["coordinates"],
                "source": source,
                "source_id": stop["id"],
                "services": [bus["service"]],
                "service_date": bus["service_date"],
            })
    scenario_sources = []
    for case_id, config in CASES.items():
        case = workspace.get_case(case_id)
        template = root / "fixtures" / "scenarios" / config["scenario"]
        scenario = json.loads(template.read_text(encoding="utf-8"))
        map_file = root / "fixtures" / "maps" / config["osm"]
        source = _source(
            template,
            map_file=map_file.relative_to(root).as_posix(),
            map_sha256=_sha256(map_file),
            provider="OpenStreetMap contributors plus saved Hamar scenario labels",
            attribution="OpenStreetMap contributors, ODbL 1.0",
            source_url=scenario["metadata"].get("planning_source")
            or scenario["metadata"].get("map_source")
            or "https://www.openstreetmap.org/",
        )
        scenario_sources.append(source)
        for journey in case["journeys"]:
            for side in ("origin", "destination"):
                endpoint = journey[side]
                places.append({
                    "id": f"preset-{case_id}-{journey['id']}-{side}",
                    "name": endpoint["label"],
                    "kind": "named_place",
                    "coordinates": endpoint["coordinates"],
                    "source": source,
                    "source_id": endpoint["id"],
                    "case_id": case_id,
                })
    return {
        "id": "hamar-local-place-index-v1",
        "generated_from_saved_data_only": True,
        "search_normalization": "Unicode casefold, whitespace and Norwegian diacritics preserved; substring match",
        "walking_scope": (
            "Search results cover the saved Hamar fixtures, not a live geocoder. "
            "Coordinates outside the selected walking extract are reported as "
            "outside coverage; points are snapped to a walking node within 75 m."
        ),
        "sources": sources + scenario_sources,
        "places": sorted(places, key=lambda item: (item["name"].casefold(), item["id"])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "fixtures" / "places" / "hamar-place-index.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
