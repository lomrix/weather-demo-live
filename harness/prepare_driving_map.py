"""Download and sanitize a rectangular OSM car-road fixture."""

import argparse
import json
from pathlib import Path

try:
    from .prepare_walking_map import prepare
    from .sanitize_driving_fixture import sanitize
except ImportError:
    from prepare_walking_map import prepare
    from sanitize_driving_fixture import sanitize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bounds", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"), required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.metadata.resolve():
        parser.error("Output and metadata paths must differ")
    entry = prepare(args.bounds, args.columns, args.rows, args.output, sanitizer=sanitize)
    entry["procedure"] = "harness/sanitize_driving_fixture.py"
    args.metadata.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output} and {args.metadata}")


if __name__ == "__main__":
    main()
