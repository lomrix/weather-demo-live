# Hamar traffic and bus reliability ? provisional project

Intended users are transport staff reviewing recurring road patterns and bus timing evidence around Hamar. These standard-library components use genuine saved samples offline. The checked briefing controller has two successful real AI runs using saved real data; recurring collection remains pending.

## Task 006: saved route coverage at three stops

Run from the repository root with standard-library Python:

```text
python harness/route_coverage_report.py --input fixtures/hamar-route-coverage-2026-10-21.json --output-dir out/route-coverage
python scripts/verify_route_coverage.py
```

The producer writes self-contained `out/route-coverage/route-coverage.html` and `route-coverage.json`. This saved 21 October snapshot inventories six verified quays at Storhamarsenteret, Hamar skysstasjon and CC Hamar from one bounded first page of 100 INN journeys. Observed routes are B21 (6 journeys, 18 calls, 10 actual/8 prediction-only), B22 (3 journeys, 6 calls, 3 actual/3 prediction-only) and 660 (1 journey, 2 calls, 0 actual/2 prediction-only). Totals: 10 distinct observed journeys, 26 calls, 13 actual and 13 prediction-only; zero unknown/cancelled. Route 660's lack of actual comparisons describes data availability, not proof of poor service.

B22 actual observations are now represented by this saved-data component. Repeated-day capture and the main AI catalogue integration remain pending; the existing AI briefing does not automatically cover B22. This is no complete city/day survey; absence from the subset does not establish absence of a service. Predictions remain separate, missing data is unknown, provider actuals are not independently verified physical events and counts are not passenger counts. No recurring patterns, causes, performance ranking or municipal benefit are demonstrated.

The new verifier uses fresh ignored `out/route-coverage-verification/checks-*/` directories and records commands, stdout/stderr, exits, assertions and `summary.json`. Mutations are synthetic software checks, not live or repeated-day experiments. The existing nine traffic cases remain unchanged. The Windows/Ubuntu workflow now also runs the route verifier; remote CI for this addition remains **pending**. See `tasks/006-route-coverage-sample.md` for local evidence.

## Task 005: repeatable offline verification

From the repository root, with standard-library Python (CI uses Python 3.12):

```text
python scripts/verify_traffic.py
```

Exit 0 and `PASS: 9/9 offline cases; zero model requests` mean all expected results were checked. An expected controller rejection passes its test; any unexpected result, timeout or failed assertion makes the verifier exit nonzero and identify the failed case. Each execution creates a fresh ignored directory under `out/traffic-verification/`, with synthetic decisions, copied/mutated inputs, per-case commands, stdout/stderr, actual exit codes, assertions and `summary.json`. Controller run paths come from each invocation's output and are checked to stay inside `out/traffic-brief/`.

Checks use saved real fixtures and synthetic decisions, only prepare/replay modes, zero model invocations and no live data. They cover reviewed fact anchors/provenance, accepted JSON/HTML content, unknown/duplicate IDs, malformed/missing input and unavailable actual statistics. Missing actuals remain unknown, while predictions remain separate. Content checks are not visual or accessibility inspection, usefulness evaluation or proof of recurring performance.

The `Traffic offline verification` GitHub workflow runs the same command on PRs targeting main, pushes to main and manual dispatch, using Ubuntu/Windows with Python 3.12. After a remote run, open the PR's **Checks** tab (or repository **Actions**) and inspect both matrix jobs and their logs. Initial GitHub run `39803550320` passed on Windows and Ubuntu. In a deliberate test exercise, commit `8724b9d` changed the correct road-total expectation 19576 to 19577; Ubuntu job `119914885500` in run `39804761955` rejected it (prepare, valid-replay and no-actuals-prepare failed; 6/9 passed, exit 1). This was an intentionally incorrect test expectation, not an application defect. Restoring 19576 locally passed all nine cases, exit 0; remote checks after this repair remain **pending**. Official action/runtime setup normally downloads components; the Python verifier is offline, without an isolated runner network sandbox. Task evidence and remaining limits are recorded in `tasks/005-offline-traffic-checks.md`.

## Task 004: checked briefing workflow

Run from the repository root (mode is always explicit):

```text
python harness/traffic_brief.py --mode prepare
```

Synthetic replay (offline, not real AI execution): create an ignored JSON decision file under `out/` so the offline replay is reproducible without relying on the temporary `out/task004-checks-domzmx58/valid.json` path from a prior run. PowerShell example:

```powershell
New-Item -ItemType Directory -Force -Path out | Out-Null
$decision = @{
    highlight_ids = @('bus.actual_max_seconds', 'road.vang_kirke.peak')
    followup_ids = @('collect_same_day_samples')
}
$decision | ConvertTo-Json -Compress | Set-Content -Path 'out/task004-synthetic-decision.json' -Encoding utf8
```

Exact synthetic contents written to `out/task004-synthetic-decision.json`:

```json
{"highlight_ids":["bus.actual_max_seconds","road.vang_kirke.peak"],"followup_ids":["collect_same_day_samples"]}
```

Replay using that reproducible path:

```text
python harness/traffic_brief.py --mode replay --decision-file out/task004-synthetic-decision.json
```

This replay is labelled OFFLINE REPLAY and never establishes AI execution. Prepare stops after computing facts and reading runtime context. Each command prints its unique directory under `out/traffic-brief/`, containing `trace.json`, `facts.json` and `prompt.txt` after valid input preparation. Checked replay also writes `checked-decision.json`, `briefing.json` and self-contained `briefing.html`. Failed runs record a reason and never reuse an older briefing as current.

Real AI execution succeeded with the existing installed/logged-in Codex CLI. Working command from the repository root:

```text
python harness/traffic_brief.py --mode codex --codex-path "C:\Users\moham\.codex\packages\standalone\current\bin\codex.exe"
```

The saved successful runs used the configured permission override. An optional `--codex-path` selects an existing executable; otherwise PATH and the known standalone Windows install are checked. No model override is used and login files are never inspected. The child uses a one-time narrowed named permission profile (read-only, .env/.env.local denied, command networking disabled), not modified permission files or bypass flags. The earlier non-model diagnostic failed with Access is denied, but the later real runs completed with this override. Successful runs do not independently prove permission enforcement or timeout/process-tree controls.

On 22 October 2026, saved runs `out/traffic-brief/20261022T143808Z-e3red74e` and `out/traffic-brief/20261022T144225Z-x1srsxg5` each recorded process exit 0, one Codex invocation, a completed turn, checked decisions and rendered HTML/JSON briefings. Both used saved real data: road observations from 20 October and bus observations from 21 October, not new live collection or synthetic decisions.

Both selected `road.vang_kirke.total` (19,576 vehicle passages), `bus.actual_count` (10 stop-call comparisons), `bus.actual_min_seconds` (-88 signed seconds) and `bus.actual_max_seconds` (289 signed seconds), with `collect_same_day_samples` and `check_early_departure_records` as follow-ups.

Reported usage was 17,513 input / 54 output tokens for `20261022T143808Z-e3red74e` and 17,514 input / 54 output tokens for `20261022T144225Z-x1srsxg5`. Both reported zero cached-input, cache-write-input and reasoning-output tokens.

The controller permits one model invocation, no controller retries, a 12,000-character prompt, 120-second child timeout, 4,096-byte decision and bounded 1 MiB stdout/1 MiB stderr capture. Tool events, failed turns and invalid selections are rejected. Reported token usage is retained when available. These are invocation/time/size controls, **not a proven hard token or monetary budget**. The model selects IDs only; program-owned verified facts/questions are rendered. Compare selection usefulness with a deterministic baseline before claiming AI superiority. Recurring acquisition, repeated-day evidence, that evaluation and a hard budget remain outstanding.

Task 004 offline checks verified all ten fact anchors, source dates/hashes, context read, a valid replay, unknown-ID rejection and malformed-input rejection; all recorded zero Codex invocations. See `tasks/004-checked-traffic-brief.md` for actual commands, runs, outputs and blocked diagnostics. HTML visual inspection remains pending.

Run separately from the repository root:

```text
python harness/traffic_report.py --input fixtures/hamar-traffic-2026-10-20.json --output-dir out
python harness/bus_timing_report.py --input fixtures/hamar-b21-timing-2026-10-21.json --output-dir out
```

Open `out/traffic-report.html` and `out/bus-timing-report.html`; matching JSON files retain provenance, detailed values and summaries. Actual verification is recorded in `tasks/002-traffic-baseline.md` and `tasks/003-bus-timing-sample.md`.

Road data: [Statens vegvesen traffic-data API](https://trafikkdata-api.atlas.vegvesen.no), three separate counters on 20 October 2026. Vehicle passages do not measure unique travellers, congestion or bus delay.

Bus attribution: Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS. [NLOD licence](https://data.norge.no/nlod/no/2.0), [Entur realtime documentation](https://developer.entur.no/open-data/realtime), [terms](https://developer.entur.no/terms-of-service), [getting started](https://developer.entur.no/docs/getting-started).

The filtered B21 snapshot contains six journeys and 18 calls at three stops from one bounded 100-journey INN response on 21 October 2026, not complete regional coverage. Other calls and vehicle/staff identifiers were excluded. The retained response hash describes the original whole response, not the fixture bytes. Source-reported actuals are provider observations, not independently verified physical events or evidence of a legal service breach. Predictions are separate; missing comparisons are unknown and cancelled calls are excluded. Negative differences are preserved.

The road and bus samples are on different dates and are not simultaneous observations. These samples do not establish recurring delay rates, passenger harm, causes or intervention success. Recurring acquisition, repeated-day evidence, usefulness evaluation and actual municipal benefit remain pending.

## Earlier weather practice exercise

Run `python server.py` and open http://127.0.0.1:8000.

Tomorrow is calculated in Europe/Oslo. Forecasts come from MET Norway Locationforecast for Hamar (60.7945, 11.0679), through a Python proxy. No dependencies or API key are needed.

Forecasts are cached in memory until MET’s `Expires` time. After expiry, the server uses `Last-Modified` for a conditional request when available. HTTP 304 means the cached forecast can be retained. Missing or invalid expiry causes revalidation on the next request. The cache resets when the server restarts.

Before running any API request, set `MET_USER_AGENT` to an application identifier with your genuine contact email or project URL, as required by MET Norway. The server refuses to contact the API when this setting is missing. Use the same identifier for connectivity checks. A successful API request verifies connectivity only; it does not verify date selection or webpage rendering.

Forecast data: MET Norway, CC BY 4.0. Low/high temperatures use hourly samples; precipitation totals appear only when hourly precipitation is available throughout tomorrow.

## Funding preparation: first component

The checker classifies a declared timeline-preparation answer and reads the source URL from the saved JSON rule. `True` means `declared_present`, not verified document contents.

The tests use synthetic answers and a saved real rule. Python's standard library is sufficient. Run from the repository root:

```text
python -m unittest discover -s eval -p check_funding_timeline.py -v
```

Expected result: four tests and `OK`.

Rule interpretation, document/date validation, AI stages and the website remain unimplemented.

## Task 001: offline source probe

The probe reads the saved public-rule excerpt in `fixtures/funding-timeline-rule.json` and generates `out/probe.json`, copying the source URL, checked date, rule ID and quote unchanged.

Run these commands separately from the repository root:

```text
python harness/probe.py
```

```text
python eval/check_probe.py
```

```text
python -m unittest discover -s eval -p check_probe_inputs.py -v
```

Expected: the producer is normally silent, the checker prints `PASS`, and three tests report `OK`. The synthetic cases cover missing input, invalid JSON and missing `source_quote`; each checks that neither the output file nor its parent directory is created.
