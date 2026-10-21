# Task 002: offline traffic baseline

Purpose: explore road-counter patterns around Hamar using genuine saved observations for 20 October 2026. This bounded traffic task supersedes the provisional funding purpose only within its scope. Existing application and funding work are preserved.

Created `harness/traffic_report.py` (Python standard library) and the exact-byte fixture `fixtures/hamar-traffic-2026-10-20.json`, copied from `C:/Users/moham/Documents/Codex/2026-10-01/i-m-starting-compulsory-ii-help/outputs/hamar-hourly-traffic-sample-2026-10-20.json`.

Acceptance: validate saved provenance, HTTP/GraphQL response, query/counter mapping, and exactly 24 distinct contiguous hours per counter at UTC+02:00; reject invalid counts and coverage before writing. Generate JSON aggregates and self-contained HTML with separate counters, hourly charts, coverage tables and visible limitations. Report success only after both files are written. Output paths are restricted to repository `out/`.

## Actual verification — 21 October 2026

Command: `python harness/traffic_report.py --input fixtures/hamar-traffic-2026-10-20.json --output-dir out`

Exit code **0**. Output:

```text
Generated C:\Users\moham\weather-demo-live\out\traffic-report.json and C:\Users\moham\weather-demo-live\out\traffic-report.html
```

A standard-library verification script executed using a PowerShell here-string piped to `python -` exited **0**. It compared source and fixture bytes, loaded actual generated JSON, asserted the acceptance values below (including 24 records and zero hours below 100% coverage for each), checked the HTML exists, and ran the two synthetic subprocesses. Fixture SHA256: `c9ff1d900626a35e9191df44ad46b895bba7e13e282fd3a14f15f9b0eae6f509`.

| Counter | Daily vehicle passages | Peak passages | Local peak interval | Records | Hours below 100% |
|---|---:|---:|---|---:|---:|
| Vang kirke | 19,576 | 1,834 | 15:00–16:00 | 24 | 0 |
| Disen øst | 19,806 | 1,831 | 15:00–16:00 | 24 | 0 |
| Vangsvegen 91 | 13,976 | 1,149 | 14:00–15:00 | 24 | 0 |

Synthetic commands used `C:\Users\moham\anaconda3\python.exe harness/traffic_report.py` with these arguments:

```text
--input C:\Users\moham\weather-demo-live\out\traffic-task002-yu7luuex\missing-hour.json --output-dir C:\Users\moham\weather-demo-live\out\traffic-task002-yu7luuex\missing-hour
--input C:\Users\moham\weather-demo-live\out\traffic-task002-yu7luuex\null-volume.json --output-dir C:\Users\moham\weather-demo-live\out\traffic-task002-yu7luuex\null-volume
```

Both subprocesses exited **1**, with empty stdout. Their respective stderr messages were:

```text
Traffic report failed: vang_kirke: expected exactly 24 hourly records. No successful new report; any existing outputs may be stale.
Traffic report failed: vang_kirke: volume must be a non-negative integer (not null or boolean). No successful new report; any existing outputs may be stale.
```

Assertions confirmed neither failure location contained generated reports. Temporary inputs and directories were removed by `TemporaryDirectory`; the genuine fixture was rechecked unchanged. These were synthetic failure checks, not live collection experiments.

Command: `python -m unittest discover -s eval -p check_funding_timeline.py -v`

Exit code **0**: `test_false_is_missing`, `test_invalid_answer_is_rejected`, `test_none_is_unknown`, and `test_true_is_declared_present` all reported `ok`; `Ran 4 tests in 0.015s`, `OK`. These existing tests concern funding, not traffic acceptance.

HTML was generated but has **not been visually inspected**. Counts are vehicle passages, not unique travellers or one-direction flows; they do not measure congestion or bus delay. Bus-data feasibility, recurring acquisition, runtime AI and the agentic coursework workflow remain outside this task. No network requests, package installation, evaluation-source edits, commits or pushes were performed.
