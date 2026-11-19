# Hamar municipal bus inventory

This is an actual official-source acquisition for 19 November 2026, not a
synthetic fixture or a live departures service. The import found **43 bus
lines, 173 route variants and 383 bus quays** whose coordinates lie inside
Kartverket's saved Hamar municipal polygon (3403). Of those variants, 142
have at least one scheduled journey on the selected date. Complete variant
stop sequences extend beyond Hamar; outside stops are preserved and labeled.

The three acquisition requests were: the official municipality geometry,
Entur stop discovery in its padded bounding box, and details for exactly the
discovered line IDs. `manifest.json` preserves the exact queries, variables,
retrieval time and SHA-256 of every response. GraphQL partial errors, missing
line IDs and altered saved source files are rejected. No API keys are used.

## Sources and limits

- Boundary: https://api.kartverket.no/kommuneinfo/v1/kommuner/3403/omrade
- Bus API: https://api.entur.io/journey-planner/v3/graphql
- Documentation: https://developer.entur.no/open-data/timetable
- Entur attribution: Inneholder data under Norsk lisens for offentlige data
  (NLOD) tilgjengeliggjort av Entur AS. Municipality geometry: Kartverket.
- Licence: https://data.norge.no/nlod/no/2.0

Selection uses platform coordinates within the actual municipal polygon,
including its holes and separate components. The Kartverket polygon declares
EPSG:4258; Entur uses WGS84 coordinates. No datum transformation is performed;
submetre boundary differences and stops exactly on a boundary remain a limit.
Discovery is complete only relative to this saved API response and filter;
an independent operator/service inventory reconciliation is still pending.
Do not claim that these 43 lines prove all possible Hamar bus services are covered.

Variants retain their direction identifiers, ordered quays, date-specific
scheduled journey IDs and encoded Entur route geometry. The selected geometry
is decoded as longitude/latitude for display. If geometry is unavailable, the
map explicitly labels its stop-to-stop schematic. The line list defaults to
the variant with most scheduled journeys on the saved date. This is not a
live guarantee of service, a current departure board or a timetable for other
dates. There is no bus-delay prediction or generalized bus-road diversion
assessment. Walking graph coverage is unchanged. B21/B23 remain the existing
dated walking-access closure comparisons.

## Offline reproduction

From the repository root:

```text
python -B -m harness.import_hamar_bus --output out/hamar-bus-catalogue.json
python -B -m unittest check_bus_catalogue -v
```

Create the output directory first if needed. Replay is byte-identical to the
saved `catalogue.json`; source checks and reproduction make zero network calls.
The browser reads `/api/bus/catalogue`, then a selected line and variant from
that saved data. An absent or invalid fixture returns unavailable rather than
silently substituting synthetic routes.

An explicitly requested new acquisition must use a **fresh** directory so it
cannot overwrite this experiment:

```text
python -B -m harness.import_hamar_bus --live --date YYYY-MM-DD --directory out/new-hamar-bus-capture
```

Live acquisition has three requests, no retry, a 30-second timeout and a
16 MiB response cap per request. Schema discovery during development is not
part of the three-request importer. Do not repeatedly download the same source
without a reason; operator feed publication and API coverage may change.
