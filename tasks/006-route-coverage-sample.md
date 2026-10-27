# Task 006: saved route coverage sample

Implemented 27 October 2026 with Python standard library only. The new saved-data inventory covers six verified quays at three Hamar locations, from the bounded 21 October first page of 100 INN journeys. This is offline saved evidence, not fresh collection, a full city/day survey or repeated-day analysis.

## Scope and provenance

Only seven task files were added/edited: `fixtures/hamar-route-coverage-2026-10-21.json`, `harness/route_coverage_report.py`, `scripts/verify_route_coverage.py`, this record, `README.md`, `docs/prompt-log.md`, `.github/workflows/traffic-offline.yml`. Existing application modules, fixtures, nine traffic checks, eval/, schema/context, report/PDF figures and permission files were preserved. Pre-existing `docs/problem-candidates.md` changes and untracked `.codex/` were left intact.

Copied the prepared fixture unchanged. Its SHA256 after normalising CRLF to LF is `9a3076076a18e7b29338c1fb0f1c05fc196d0ba10470a66e643eceb692560e1f`; the verifier exercises both LF and CRLF fixture copies while each report retains the exact original input-byte hash. The original whole-response hash is separately retained: `72faadd1e586e333a1bb77f9320e56aa23a7622e7b53d6a58d12c34b697bc58d`. Reviewed the independent supervising reference before implementation. No live data requests, additional model calls, package installation, scheduling, commit or push.

## Actual local verification

Commands run from the repository root:

```text
python harness/route_coverage_report.py --input fixtures/hamar-route-coverage-2026-10-21.json --output-dir out/route-coverage
python scripts/verify_route_coverage.py
python scripts/verify_traffic.py
git diff --check
```

Producer exited **0**, writing `out/route-coverage/route-coverage.json` and `route-coverage.html`.

Route verifier exited **0**, **24/24** offline cases passed; evidence: `out/route-coverage-verification/checks-9psjpyqp/summary.json`. Each case directory retains its command, actual stdout/stderr/exit and assertions in `result.json`. The initial 17-case run also passed (`checks-yo14tpxa`); the expanded run is the final evidence.

Cases: valid fixture with independent per-route/total anchors, provenance, stop mapping, interpretation limits and HTML values; LF fixture copy; CRLF fixture copy; duplicate journey; duplicate call; malformed actual timestamp; remove all actual fields (0 actual, 13 prediction-only, 13 unknown); unknown quay; mismatched quay/name; conflicting published name; missing input; invalid input preserves earlier reports; missing timestamp timezone; cancelled call with invalid supplied timestamp; strict cancellation boolean; unexpected vehicle field; impossible service date; cancellation precedence; HTML escaping; strict order type; invalid source hash; wrong quay metadata; another valid service date; another well-formed line. Mutated copies are synthetic checks only. Expected rejections verify useful reasons and absence of new output directories, or unchanged existing report sentinels.

Traffic verifier exited **0**, **9/9** existing offline cases passed; evidence: `out/traffic-verification/checks-y3fdb33d/summary.json`. Cases remain unchanged: prepare, valid-replay, unknown-highlight, duplicate-highlights, duplicate-followups, malformed-time, missing-input, no-actuals-prepare, unavailable-actual. Earlier run `checks-godwnznc` also passed. Both verifiers report zero model requests; no network collection was performed.

Repository-wide `git diff --check` exited **1** solely for the pre-existing unrelated `docs/problem-candidates.md:26: new blank line at EOF.` This file was preserved. A separate whitespace check limited to the three permitted files exited **0** after the portability repair.

## Findings and remaining work

B21 / INN:Line:21: 6 journeys, 18 calls, 10 actual, 8 prediction-only. B22 / INN:Line:22: 3 journeys, 6 calls, 3 actual, 3 prediction-only. 660 / INN:Line:660: 1 journey, 2 calls, zero actual, 2 prediction-only. Total: 10 journeys, 26 calls, 13 actual, 13 prediction-only, zero unknown/cancelled. Route 660 has no actual comparisons in this sample; that is not proof of poor service.

B22 actual observations are represented in this saved-data component. Repeated-day capture and the main AI catalogue integration remain pending. The existing AI briefing does not automatically cover B22. Missing data stays unknown, predictions remain separate, source actuals are not independently verified physical events, and counts are not passenger counts. Absence from this subset is not absence of a service. No recurring patterns, causes, ranking or demonstrated municipal benefit are established.

The Windows/Ubuntu workflow adds the new verifier as a second run step, retaining existing triggers, permissions, timeout and official action versions. **Remote CI remains pending** until actually run. HTML content was checked programmatically; visual/accessibility review remains pending. No protected-code defect was revealed by the local checks.
