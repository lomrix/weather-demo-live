# Task 007: one-request Entur capture, tested offline first

Implemented 27 October 2026 using Python standard library only. This task adds a bounded acquisition component for later dated sampling; it does not establish recurring delays, full Hamar coverage, correlation, passenger impact or integration with the existing AI briefing.

## Scope and schema

Allowed implementation surfaces were the collector, its independent verifier, this record, README, prompt log and one additional offline workflow step. Existing fixtures, producers, verifiers, `eval/`, context/schema, permissions and unrelated work were preserved. No live API request, model request, installation, commit or push was made.

`harness/collect_bus_sample.py` supports:

- `dry-run` (the default): prints endpoint, `ET-Client-Name`, `Accept`, one-request/5 MiB/20-second bounds and destination, with zero network calls and zero filesystem mutations.
- `replay`: reads synthetic SIRI 2.0 XML only, never contacts Entur, and records synthetic/offline status without inventing provider retrieval time.
- `live`: explicit opt-in, one GET to the fixed INN endpoint with normal HTTPS verification, no pagination/retry/redirect follow-up, bounded body read and local lock/cooldown coordination.

The versioned normalized snapshot schema is `bus-collection-1`. It contains only public line identity/name, direction, service date, journey reference, provider `RecordedAtTime`, supplied cancellation/monitoring flags, call-group identity, selected quay identity/name, order and supplied aimed/actual/expected times. XML booleans accept only `true`, `false`, `1` or `0`; missing `MoreData` remains null/unknown. Unknown selected values remain absent; arrival-only actuals do not create departures. Vehicle/operator/staff/contact/free-text and other provider fields are discarded. The six approved quays are the Task 006 public mapping. Unknown quays are filtered; malformed selected records, duplicate selected identities and contradictory values fail visibly.

Successful runs contain atomic `snapshot.json` and `manifest.json` under a unique ignored output directory. The manifest records mode, synthetic status, execution times, fixed request metadata, safe response headers, status, byte count, exact response-byte SHA256, snapshot-byte SHA256, provider timestamps, counts, line refs, selection and MoreData state, NLOD attribution/licence, filtering disclosure and honest limitations. Empty selected output is an `empty_success`, not a network failure. Failed runs contain a failed manifest only and do not replace earlier output.

## Offline verification

Commands run from the repository root:

```text
python scripts/verify_bus_collection.py
python scripts/verify_route_coverage.py
python scripts/verify_traffic.py
```

The new verifier uses synthetic XML and mocked transport only. Its cases cover dry-run no-mutation behavior, default CLI dry-run and CLI timestamp rejection, an offline network guard, valid replay and projection, formatting/prefix variation, namespace/envelope/DOCTYPE/status/delivery-error/XML failures, empty and unselected malformed selection, missing/arrival-only values, duplicate journey/call, malformed timestamps, invalid booleans, selected-name/date validation, source-field and provider-metadata canaries, mocked one-request live success, actual opener/body-limit/headers/timeout/close behavior, received-invalid metadata preservation, 429/503/no-retry and bounded transport failures, moving-clock Retry-After receipt deadlines, atomic publication failure and prior-run preservation, cooldown/lock behavior, replay cooldown isolation and missing replay input.

Final local results:

- `python scripts/verify_bus_collection.py`: **exit 0**, **35/35** offline cases, zero model/live requests. Evidence: `out/bus-collection-verification/checks-8fdzn_1q/summary.json`.
- `python scripts/verify_route_coverage.py`: **exit 0**, **24/24** offline cases, zero model requests. Evidence: `out/route-coverage-verification/checks-z9h7mfxg/summary.json`.
- `python scripts/verify_traffic.py`: **exit 0**, **9/9** offline cases, zero model requests. Evidence: `out/traffic-verification/checks-s813lq9v/summary.json`.
- Whitespace checks restricted to the four repair files passed; remote CI and genuine live preflight remain pending.

The workflow retains its existing triggers, matrix, permissions, timeout and action versions and adds only the third offline verifier step. Scheduled polling, pagination, multi-sample deduplication, delay aggregation, static timetable denominators, report/AI integration and usefulness evaluation remain later work.
