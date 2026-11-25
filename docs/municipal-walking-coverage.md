# Hamar municipal walking coverage

Implemented 24–25 November 2026. This replaces the small city-only extract in
the default walking workspace; historical Ringgata, Koigen, bus-access and
driving cases remain separate so their original comparisons are reproducible.

## Search and routing

- House-number lookup queries Kartverket's public address API for Hamar
  municipality, code 3403. It is not restricted to selected example addresses.
- 564 named roads/paths from the municipal OSM source are searchable offline.
  A street result selects a representative point; choosing a house number is
  more precise. Saved bus stops and named places remain searchable as well.
- New addresses and streets select the municipal walking network automatically.
  The other selected custom endpoint is retained.
- Normal walking starts with no closure projects. Hypothetical changes are
  optional; Koigen's explicit source-review/confirmation requirement is retained.
- Phone planning uses the same address and routing services as desktop.

## Source and policy

The 24 November OSM query returned 8,415 highway ways and 74,403 source nodes
for the Hamar administrative area. The sanitized snapshot retains only
geometry, road/path names and allowlisted access-related tags. No contributor
account, contact, owner, resident or apartment fields are retained.

The resulting walking graph contains 78,522 nodes and 82,295 links across
8,301 accepted ways. It includes residential/service streets and walking paths;
motorways, motorroads, explicitly prohibited/private pedestrian access and
unsupported conditional restrictions are excluded. Pedestrian one-way tags are
respected. Explicitly blocked nodes interrupt connections. Long mapped edges
are subdivided to no more than about 50 m, while preserving the original
rounded segment distance, to improve rural network resolution. Request-local endpoint projection now
splits existing links at the selected points rather than relying on the nearest
vertex. Access offsets remain excluded and unverified. Close parallel roads are not joined without a shared mapped node.

There are 21 disconnected components; the largest contains 77,992 nodes.
These are graph diagnostics, not an accuracy or municipal-address coverage
percentage. Importing all ways returned for an area does not prove that OSM
contains every real road, entrance or pedestrian connection. The app reports
missing/disconnected connections rather than inventing a route. Surface,
slope, steps and crossing safety are not established by route availability.

The OSM area defines acquisition; the existing official Kartverket municipal
polygon supplies the displayed boundary. Complete ways can extend beyond that
boundary. The manifest pins both source and boundary hashes. The base map is
geographic context; routing uses this saved network, not live traffic.

## Reproduce without network or a model

From the repository root:

```text
python hamar_workspace.py --open
python -B -m unittest check_municipal_walk check_address_search check_place_search -v
python -B -m harness.prepare_municipal_walk --source fixtures/maps/hamar-municipality.json --output out/municipal-replay-new
```

The output directory must be new. Replay recreates the source and street index
byte-identically and writes source/count/hash metadata. The app checks the saved
map against its manifest before using it. To acquire a new source explicitly:

```text
python -B -m harness.prepare_municipal_walk --live --output out/municipal-source-new
```

This makes one fixed-endpoint Overpass request, with no redirects/retries, a
60-second server query setting, 75-second client socket timeout and 32 MiB body
cap. Those settings are not a guaranteed end-to-end wall-clock limit. It writes
to a new output directory, never replaces the checked fixtures automatically,
and does not start any background refresh or model request. A new acquisition
may differ from the pinned 24 November snapshot and requires review.

## Verification evidence

Real Kartverket results selected during development included Seminargata 13,
Gåsbuvegen 1045 and Hjellumvegen 120. On the saved municipal graph the routes
from Seminargata 13 originally measured 13,786 m and 5,162 m respectively with
nearest-vertex snapping. Those are historical development measurements; the
current edge-projection evaluator and its before/after results are documented
in `exam-readiness.md`. These are modeled
network distances, excluding straight-line address snap offsets; they are not
verified door-to-door walking instructions.

Phone-sized browser verification covered the Gåsbu route, offline Høyvangvegen
street lookup and routing during a simulated address-service outage, the
Koigen 323 m/593 m confirmation flow and returning from that demo to municipal
address planning. Synthetic access/one-way/disconnection tests are separate
from these source-backed checks. Final test output is saved locally under
`out/municipal-regression.log`; it is not itself a live model experiment.

Sources: [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
[Kartverket address API](https://api.kartverket.no/adresser/v1), and the existing
boundary provenance in `fixtures/transit/hamar/README.md`. OSM-derived data is
ODbL 1.0; Kartverket address/boundary data retains CC BY 4.0 attribution.

Current consolidated checks and remaining human evidence: [exam readiness](exam-readiness.md).
