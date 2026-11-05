# Fixed OSM fixtures

These are fixed OpenStreetMap XML extracts used by the demonstrated walking
workflow. They retain the OSM `bounds` element and the root
`copyright`/`attribution`/`license` provenance:
OpenStreetMap contributors, ODbL 1.0.

The copies contain only nodes referenced by walking ways and the `highway` and
`foot` tags used by [`harness/import_hamar_osm.py`](../../harness/import_hamar_osm.py).
Contributor/change attributes (`user`, `uid`, `changeset`, `timestamp`, and
`version`), relations, non-walking ways, and other tags were removed. No
personal contact tags remain. The original download hash is intentionally
separate from the hash of each submitted fixture.

To reproduce a fixture from the documented API URL, download the XML without
editing it, then run:

```text
python harness\sanitize_osm_fixture.py --input original.osm --output fixtures\maps\sanitized.osm
```

The sanitizer uses only Python's standard library and applies the same walking
policy as the importer: `highway=footway`, `path`, `pedestrian`, or
`cycleway`, or `foot=yes`/`foot=designated`, with `foot=no` taking precedence.
The checked hashes, source URLs, retained fields, removed fields, and route
distance parity are recorded in [`manifest.json`](manifest.json).
