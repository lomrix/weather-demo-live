# Prompt log

## Task 005 offline verifier, 22 October 2026

Implemented the supplied five-file brief: a portable standard-library verification command, Ubuntu/Windows GitHub workflow and reproduction records. Local Python 3.12 checks passed all nine prepare/synthetic replay cases with zero model invocations, including duplicate rejection and missing-actual boundaries. Evidence is under `out/traffic-verification/`; remote GitHub execution remains pending. No application/eval/fixture/permission changes, live requests, model calls, installs, commits or pushes.

These entries describe two real events from 1 October 2026. They were written on 5 October 2026.

## 1. API identification correction

> Before making the request, ask me for genuine contact information
> or a project URL for the User-Agent. Do not invent one. Use the
> same identifier in the application and this test. Treat this as
> an API connectivity check, not proof that the webpage shows
> tomorrow’s forecast correctly.

The proposed MET request used only “local development” as contact information. The user asked the agent to request genuine contact information or a project URL, and to use the same identifier for the application and the test.

The fallback was removed. `MET_USER_AGENT` became required. The user's actual contact information is not recorded here.

## 2. Forecast caching correction

> Correct only the forecast caching in server.py. Respect MET’s
> Expires header and use its Last-Modified value for conditional
> requests after expiry. Handle HTTP 304 by retaining the cached
> forecast. Do not make a live request yet. Explain the change.

The server initially cached forecasts for a fixed ten minutes. The user asked the agent to respect `Expires`, send `If-Modified-Since` using `Last-Modified`, and retain cached data on HTTP 304.

The saved implementation was inspected with Codex assistant help. The agent reported passing mock checks, but their raw output was not independently inspected.

## Separate forecast comparison

One user-run forecast was compared with saved real API data with Codex assistant help. The displayed temperature, wind, condition, sampled low/high, and daily precipitation matched that response.

## Remaining issues

- Incomplete-day handling.
- Stale display after a failed refresh.
- An unexplained connection-aborted error.

## Strict-output schema repair, 22 October 2026

This entry supersedes the earlier statement that real Codex mode had never been run. The saved real attempt `out/traffic-brief/20261022T142330Z-rj9o7w_f` failed before producing a decision or final briefing. Its `codex-events.jsonl` records HTTP **400**, `invalid_request_error`, code `invalid_json_schema`, parameter `text.format.schema`, with the actual API rejection:

```text
Invalid schema for response_format 'codex_output_schema': 'schema.properties.highlight_ids.uniqueItems' is not permitted when strict is true.
```

The trace records one Codex invocation, process exit **1**, status `failed`, failure reason `Codex process exited 1` and null token usage. This is evidence of a schema rejection, not successful real AI verification.

Removed `uniqueItems` from both `highlight_ids` and `followup_ids` in `context/traffic-brief.schema.json`. All other schema constraints are preserved: object type, required keys, no additional properties, string items, highlight bounds 2 to 4 and follow-up bounds 1 to 2. The Python controller and its independent duplicate checks were not changed.

Offline verification used synthetic decisions written under `out/task004-schema-repair-qresi2n2/`. A standard-library PowerShell here-string piped to `python -` ran these commands and asserted exit codes, final-file presence/absence, synthetic labels in both successful files, rejection messages and zero Codex invocations. The wrapper exited **0**. Exact commands, stdout, stderr, exit codes and file checks are retained in `out/task004-schema-repair-qresi2n2/results.json`.

```text
python harness/traffic_brief.py --mode replay --decision-file C:\Users\moham\weather-demo-live\out\task004-schema-repair-qresi2n2\valid.json
```

Exit **0**; run directory `20261022T142631Z-309otu7q`. Both `briefing.json` and `briefing.html` were produced and contain `OFFLINE REPLAY - synthetic decision; not real AI execution`. stderr was empty.

```text
python harness/traffic_brief.py --mode replay --decision-file C:\Users\moham\weather-demo-live\out\task004-schema-repair-qresi2n2\duplicate-highlights.json
```

Exit **1**; run directory `20261022T142631Z-iiv5dtra`. Neither `briefing.json` nor `briefing.html` exists. stderr:

```text
FAILED: Duplicate or unknown highlight_ids; no successful current briefing; older runs may be stale.
```

```text
python harness/traffic_brief.py --mode replay --decision-file C:\Users\moham\weather-demo-live\out\task004-schema-repair-qresi2n2\duplicate-followups.json
```

Exit **1**; run directory `20261022T142631Z-74ke9gf5`. Neither `briefing.json` nor `briefing.html` exists. stderr:

```text
FAILED: Duplicate or unknown followup_ids; no successful current briefing; older runs may be stale.
```

All three runs recorded **zero Codex invocations**. These are offline synthetic checks, not live experiments. At the time of this repair, real AI verification with the repaired schema was pending; no further real model request was made during the repair. The later successful runs are recorded below. No controller, eval, fixture or permission changes, package installation, commit or push was performed. Only the schema and the two requested records were edited; generated check artifacts are under out/.

## Successful real runs reviewed, 22 October 2026

Reviewed saved evidence for `20261022T143808Z-e3red74e` and `20261022T144225Z-x1srsxg5` under `out/traffic-brief/`: both exited 0 with one real Codex invocation and checked HTML/JSON briefings using saved real road/bus data. Both selected `road.vang_kirke.total`, `bus.actual_count`, `bus.actual_min_seconds`, `bus.actual_max_seconds`; follow-ups were `collect_same_day_samples` and `check_early_departure_records`. Reported input/output tokens: 17,513/54 and 17,514/54 respectively; all other reported usage fields were zero.

Updated README, SPEC and Task 004; preserved the dated schema failure/repair. Recurring collection, usefulness evaluation and a hard token/cost budget remain pending. This review made no model calls or network requests.
