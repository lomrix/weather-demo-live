# Fixed OSM fixtures

These are fixed OpenStreetMap XML extracts used by the demonstrated walking
and driving workflows. They retain the OSM `bounds` element and the root
`copyright`/`attribution`/`license` provenance:
OpenStreetMap contributors, ODbL 1.0.

The walking copies contain only nodes referenced by walking ways and the `highway` and
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

`hamar-wider.osm` covers both preset areas and the land between them
(lat 60.796-60.810, lon 11.040-11.090). The OSM API refused that whole box
(more than 50000 nodes), so it was downloaded as two unedited tiles, merged with
[`harness/merge_osm_tiles.py`](../../harness/merge_osm_tiles.py) (de-duplicated by
id, bounds unioned), then sanitized with the command above. The manifest records
both tile URLs and hashes, the merged-file hash, the retrieval time and the
sanitized hash.

`hamar-urban.osm` is the larger rectangular study area documented in the
main README. It was prepared with [`harness/prepare_walking_map.py`](../../harness/prepare_walking_map.py),
which downloads a configurable grid, validates bounds, merges and sanitizes
the tiles, checks references and emits a manifest entry. The rectangle is not
an official administrative boundary and does not guarantee complete walking
coverage. Individual tile hashes and retrieval times are in the manifest.

`hamar-urban-roads.osm` covers the same rectangle but retains road ways and
their car access, direction and junction tags, plus road-node barrier/access
tags. Its separate sanitizer and retained fields are recorded in its manifest
entry; the top-level walking policy does not apply to it. Contributor attributes,
relations, unrelated tags and contact tags are removed. See the main README
for supported rules, limitations and the configurable rebuild command.


## Municipal walking snapshot (24 November 2026)

`hamar-municipality.json` captures all highway ways returned by the OSM Hamar
municipal area (ref 3403, admin level 7) query, including their complete node
references. It contains 8,415 ways and 74,403 source nodes, before routing
policy filters. Only geographic, highway, name and access-related fields are
retained; contributor metadata and contact fields are discarded. The exact
query, acquisition time, OSM base timestamp, raw-response hash and sanitized
hash are preserved. `manifest.json` also pins the existing official Kartverket
municipal boundary and the generated street index.

`hamar-municipality-streets.json` is a deterministic projection of the named
ways. The routing graph is built by `harness/municipal_walk.py`; old urban,
Ringgata and Koigen snapshots remain independent. Source: OpenStreetMap
contributors, ODbL 1.0; the boundary source retains its Kartverket attribution.

Details and reproduction commands: [municipal coverage](../../docs/municipal-walking-coverage.md).
