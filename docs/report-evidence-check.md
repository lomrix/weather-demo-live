# Report evidence check — 25 November 2026

This is a bounded audit of repository evidence. It is not a completed review
of the current Overleaf draft. The teammate's unpublished experiments and human
observations remain unverified until their supporting records are shared.

## Claims supported by saved evidence

| Claim available for the report | Supporting record | Scope that must accompany it |
| --- | --- | --- |
| Default walking uses a municipal OSM snapshot with 82,295 links, 78,522 nodes and 564 searchable road/path names | `municipal-walking-coverage.md`, `../fixtures/maps/manifest.json`, municipal import/checks | Saved network and access policy; not every physical entrance or safe pedestrian connection independently verified |
| Address lookup uses official Hamar municipal address queries | `../harness/address_search.py`, `../check_address_search.py` | Online dependency; named-street and saved-place fallback is narrower than live house-number lookup |
| 43 bus lines, 173 variants and 383 quays were found inside the saved municipal polygon | `../fixtures/transit/hamar/README.md` and hashed source manifest | Snapshot for 19 November; not live departures or independent proof of all services; general closure impacts are not assessed for every line |
| The frozen municipal journey suite improved from 13/14 to 14/14 after endpoint projection repair | `../fixtures/evaluation/runs/2026-11-25-before-edge-snap/`, `../fixtures/evaluation/runs/2026-11-25-edge-snap/` | Software/graph expectations, including three deliberate equal/rejection cases; 11 routed cases; not human or physical-route accuracy |
| The original clean checkout exposed a source-hash failure; Linux additionally exposed replay newline differences | `../fixtures/evaluation/runs/2026-11-25-place-index-portability/` | Preserve failed runs and causal repairs; do not present the earlier working-tree pass as sufficient portability verification |
| The corrected clean-copy suite passed 230 tests and 14/14 journey cases; final PR and post-merge checks passed on Ubuntu/Windows | `exam-readiness.md`; GitHub PR #32 and Actions runs linked below | The preserved earlier full-run artifact has 228 tests; final runs have 230. Identify the run/revision used for each number |
| Koigen's modeled interruption changes a 323 m baseline to 593 m (+270 m) | Source-linked notice/scenario fixtures and Koigen checks | Notice closure dates and geometry remain unknown. User confirmation permits a simulation, not a verified real closure boundary or signed diversion |
| Eight actual local model requests were compared against a narrow fixed baseline over four cases | `notice-evaluation-2026-11-19.md`, `../fixtures/notice-evaluation/runs/2026-11-19/results.json` | One known development notice plus three invented diagnostics. Exact-match scores are not semantic real-world accuracy. No demonstrated model superiority or review-time saving |
| Phone walkthrough and direct View stops improvement were checked | `phone-review-walkthrough.md`, 17 focused bus/static tests | Developer browser checks at 390 × 844; no completed independent human study. This follow-up is separate from merged PR #32 |

Final corrected PR check: https://github.com/lomrix/weather-demo-live/actions/runs/45623491091

Post-merge check for `28527ac`: https://github.com/lomrix/weather-demo-live/actions/runs/45624153993

The old 183-test count in a draft should be tied to its actual revision and log
or replaced with the relevant verified final run. Do not add distinct runs
(228 full, 59 focused, 230 final and 17 UI-focused) into one inflated test total.

## Claims still awaiting evidence

- Independently measured usability, usefulness, trust or willingness to pay.
- Teammate's held-out notice/model results: obtain the actual source/reference
  files, scripts, code revision, model digests/options and raw outputs. Preserve
  missing metadata explicitly rather than reconstructing it as contemporaneous.
- Full physical-address/entrance coverage, step-free safety and current road
  reopening confirmations. Availability of a route does not establish these.
- Continuous background notification delivery or live bus operation. Saved
  in-app alert checks and dated timetables should be described as implemented.
- Professor's answer about meeting reports and genuine supporting records.
  The planned question is on 26 November; no answer has been received.

## Next-session report review

Read the current Overleaf source/PDF and check every numerical claim against
this table. Keep the wider product vision and possible payer groups as reasoned
future work. Describe implemented behavior, tested behavior and planned work
separately. Check the brief's main-page allowance, appendices, evidence links
and final submission revision. The current white paper has not been certified
complete, compliant or A-level by this bounded audit.
