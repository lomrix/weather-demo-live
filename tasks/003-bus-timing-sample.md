# Task 003 — offline B21 timing sample

Purpose: provide checkable departure comparisons for transport staff exploring Hamar bus reliability. Scope is one saved, filtered Entur snapshot, not recurring acquisition, runtime AI or a completed agentic workflow. The road sample is from 20 October and this bus sample from 21 October 2026; they are not simultaneous observations.

Created the exact-copy fixture, standard-library `harness/bus_timing_report.py` and this record. Updated README.md and SPEC.md for the provisional traffic direction, preserving earlier exercise instructions. AGENTS.md changes are limited to purpose and task-based verification guidance. No existing files were moved/deleted; no eval source, road implementation or road fixture was edited. No network/AI requests, package installation, commits or pushes were performed.

## Acceptance and implementation

Validate saved HTTP/provenance/attribution, B21/stop selection, nested value/list fields, journey/call identity, cancellation flags and every non-null provided timing field before writing. Retain arrival/departure times, source groups and public identifiers. Duplicate journeys/call orders and malformed supplied timestamps fail. Non-cancelled actual-minus-aimed comparisons remain separate from expected-minus-aimed predictions; unknown comparisons retain null differences. Cancelled calls are excluded. Output stays under out/; failure messages explicitly warn that older outputs may be stale. Success is printed only after both reports are written.

HTML includes local departure times, separate categories, source/licence attribution, filtered-data disclosure and sample limitations. Actual times are source-reported provider observations, not independently verified physical events or legal-breach evidence. Original-response SHA256 is labelled as applying to the whole source response, not the filtered fixture.

## Actual commands and results — 21 October 2026

```text
python harness/bus_timing_report.py --input fixtures/hamar-b21-timing-2026-10-21.json --output-dir out
```

Exit **0**, stdout:

```text
Generated C:\Users\moham\weather-demo-live\out\bus-timing-report.json and C:\Users\moham\weather-demo-live\out\bus-timing-report.html
```

Independent standard-library verification was executed with a PowerShell here-string piped to `python -`, exit **0**. It compared source/fixture bytes; loaded generated JSON; checked all 18 rows against native source identities, groups, supplied times, flags, missingness, categories and independently recomputed differences; asserted every acceptance anchor; and launched the two synthetic commands below. Fixture SHA256: `c5fcc4184b8c2ff2ed8e155245bbc040880ef48d88c98966b7f351d8c68139f2` (distinct from the original-response hash).

Actual row verification output (journey suffix / stop / category / signed seconds):

```text
53561 Storhamarsenteret actual 133
53561 Hamar skysstasjon actual -88
53561 CC Hamar actual 177
53562 Storhamarsenteret actual -56
53562 Hamar skysstasjon actual 113
53562 CC Hamar prediction_only 58
53563 Storhamarsenteret prediction_only 259
53563 Hamar skysstasjon prediction_only 139
53563 CC Hamar prediction_only 139
53462 CC Hamar actual 289
53462 Hamar skysstasjon actual 241
53462 Storhamarsenteret prediction_only 241
53463 CC Hamar prediction_only 166
53463 Hamar skysstasjon prediction_only 46
53463 Storhamarsenteret prediction_only 46
53461 CC Hamar actual 72
53461 Hamar skysstasjon actual 47
53461 Storhamarsenteret actual 156
```

Verified: six journeys, 18 calls, ten actual, eight prediction-only, zero unknown/cancelled. Actual-only signed seconds: sum **1084**, minimum **-88**, maximum **289**. Each stop has six calls: CC Hamar 3 actual/3 prediction-only; Hamar skysstasjon 4/2; Storhamarsenteret 3/3. Exact example timestamps were checked: Storhamarsenteret 15:41:00 to source-reported actual 15:43:13 = +133 actual seconds; CC Hamar 16:10:00 to expected 16:10:58 = +58 predicted seconds, all on 21 October at UTC+02:00.

Synthetic checks (not live experiments), executed as subprocesses:

```text
C:\Users\moham\anaconda3\python.exe harness/bus_timing_report.py --input C:\Users\moham\weather-demo-live\out\bus-task003-x5gp9gup\malformed-actual.json --output-dir C:\Users\moham\weather-demo-live\out\bus-task003-x5gp9gup\malformed-actual
```

Exit **1**; stdout empty; stderr:

```text
Bus timing report failed: Malformed timestamp: 'not-a-date'. No successful new report; older outputs may be stale.
```

Assertion verified that no output directory/report files were created.

```text
C:\Users\moham\anaconda3\python.exe harness/bus_timing_report.py --input C:\Users\moham\weather-demo-live\out\bus-task003-x5gp9gup\no-actuals.json --output-dir C:\Users\moham\weather-demo-live\out\bus-task003-x5gp9gup\no-actuals
```

Exit **0**; stderr empty; stdout:

```text
Generated C:\Users\moham\weather-demo-live\out\bus-task003-x5gp9gup\no-actuals\bus-timing-report.json and C:\Users\moham\weather-demo-live\out\bus-task003-x5gp9gup\no-actuals\bus-timing-report.html
```

Assertions verified zero actual comparisons, eight prediction-only, ten unknown, zero cancelled; actual-only sum/min/max all null. RecordedCalls membership did not become an actual measurement. Synthetic inputs/output are retained under out/; genuine fixture was rechecked unchanged.

```text
python -m unittest discover -s eval -p check_funding_timeline.py -v
```

Exit **0** (confirmed in a separate command): four funding tests (`test_false_is_missing`, `test_invalid_answer_is_rejected`, `test_none_is_unknown`, `test_true_is_declared_present`) all `ok`; `Ran 4 tests in 0.002s`, `OK`. These are earlier funding regressions, not bus acceptance tests.

`git diff --check` exited **0**, with no output. `git diff --name-only; git status --short` exited **0** and showed only the six permitted project files plus the pre-existing untracked `.codex/` directory. Generated/synthetic artifacts are under ignored out/.

HTML was generated but not visually inspected. Repeated-day reliability, passenger harm, causes, legal breach and municipal benefit are not established. Review the generated files before staging; the broader workflow remains pending.
