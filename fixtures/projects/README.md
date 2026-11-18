# Saved walking-project alert fixtures

These are reproducible **synthetic** records for in-app alert testing. They are
not municipal notices, live project feeds or observed works.

- `hamar-walking-projects-base.json` is the previously seen snapshot.
- `hamar-walking-projects-current.json` is the current snapshot and extends
  `ringgata-extension-demo` from 2026-11-17 to 2026-11-24.

Each record includes its saved source file, source label/URL, retrieval time,
attribution and a SHA-256 computed by the server. The walking restrictions
refer only to fixed section IDs in the saved `hamar-urban` graph.

Alert checks occur when the app opens or when a person selects **Refresh
journey alerts**. A refresh compares the previous browser-local snapshot with
the saved current snapshot, calculates the saved journey through the existing
Python routing engine, and returns only source-backed changes and route
effects. This is explicit refresh, not continuous monitoring.

An expired scheduled end date produces **Scheduled end passed; reopening
unconfirmed**. Only `reopening_confirmed: true` with an explicit source record
produces a reopening-confirmed alert. Missing project files, invalid records,
unknown case/section IDs and now-unresolved saved journeys are reported as
unavailable instead of silently ignored.
