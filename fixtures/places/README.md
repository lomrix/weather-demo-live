# Saved Hamar place index

`hamar-place-index.json` is generated from local, checkable fixtures. It is
not a live geocoder and does not fetch place data at runtime.

Sources:

- The saved B21 fixture `fixtures/scenarios/hamar-b21-2026-11-12.json`.
- The saved B23 fixture `fixtures/scenarios/hamar-b23-2026-11-12.json`.
- Named journey endpoints from the saved Hamar walking scenarios and their
  sanitized OpenStreetMap fixtures, with fixture hashes and ODbL attribution.

The builder deduplicates bus stops with the same normalized name and
coordinates, records NSR quay IDs, service/date provenance, Entur NLOD
attribution and source fixture hashes. Scenario endpoints retain the scenario
file, map file/hash, case and OSM source metadata. Reproduce the index with:

```text
python harness\build_place_index.py
```

Limitations:

- Coverage follows the two saved bus trips and the preset walking journeys;
  it is not a complete list of Hamar places or bus stops.
- Search only matches a normalized substring of the saved display name.
- A search result outside the selected walking extract remains selectable but
  receives an outside-coverage result during snapping.
- Bus-stop coordinates identify saved quays, not doors or accessibility.
- Snapping is limited to 75 m from the selected walking network and does not
  verify physical continuity, legal access, crossing safety or accessibility.
- Index source dates are historical. Current stop names and locations are not
  inferred or continuously checked.
