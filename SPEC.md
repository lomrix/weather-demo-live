# Provisional problem and users

Transport staff around Hamar need checkable evidence when investigating recurring road patterns and bus reliability. This direction is provisional; comparison with existing planning tools and municipal usefulness remain unresolved. The earlier funding exercise is preserved, with reproduction instructions in README.md; the earlier weather exercise files were removed and remain only in Git history.

# Intended workflow and checkable success

Collect a bounded permitted public-data sample, validate provenance and completeness, analyse observations separately from predictions, then produce a sourced briefing with independently checked claims and explicit unknowns. Future runtime AI requires budget/stop conditions and independent checks. No collection service is started by the offline tasks.

Every reported value must trace to saved source rows and public identifiers. Preserve journey, direction, stop and call-order identities. Reject duplicates and malformed supplied timestamps. Actual comparisons require actual and aimed departure times; predictions remain separate, missing comparisons remain unknown, and cancelled calls are excluded. Independent source-row checks and synthetic failure cases must support conclusions. Do not infer congestion, legal service breach or municipal benefit from the samples.

# As built versus pending

Task 002 generates offline HTML/JSON for three road counters on 20 October 2026, validating 24 contiguous local hours and reporting separate totals, peaks and coverage. Vehicle passages do not measure unique travellers, congestion or bus delay.

Task 003 adds offline HTML/JSON for a filtered Entur B21 snapshot on 21 October 2026. Small-snapshot bus access is demonstrated by the saved successful response; this implementation makes no live requests. It separates source-reported actual departure differences, predictions, unknowns and cancellations. Actual verification is recorded in the task record. The two samples are on different days and are not simultaneous evidence.

Task 004 connects the existing analysis functions into an explicit prepare/replay/codex controller. Every run validates fixtures afresh (never stale generated reports), computes a fact catalogue with source dates/URLs, evidence identifiers and separate input hashes, reads runtime context, and constructs a bounded prompt. AI's demonstrated role is prioritising known finding IDs and permitted follow-up IDs only. A separate program check requires road and bus actual evidence, rejects fabricated/duplicate/unavailable selections and renders only verified values and fixed questions with mandatory caveats and attribution. Trace files record stages, failure reasons, mode, invocation count and reported token usage.

Prepare and clearly synthetic offline replay/rejection paths are verified; they make zero Codex invocations. The real-mode branch is implemented with one saved-login Codex subprocess, a narrowed read-only/no-command-network permission override, event checks, timeout and size limits. Earlier non-model diagnostics were blocked by Access is denied; subsequent real runs completed with the configured override. Independent proof of permission enforcement and timeout/process-tree controls remains outstanding.

On 22 October 2026, saved runs `out/traffic-brief/20261022T143808Z-e3red74e` and `out/traffic-brief/20261022T144225Z-x1srsxg5` each recorded process exit 0, one Codex invocation, a completed turn, checked decisions and rendered HTML/JSON briefings. Both used saved real data: road observations from 20 October and bus observations from 21 October, not new live collection or synthetic decisions.

Both selected `road.vang_kirke.total` (19,576 vehicle passages), `bus.actual_count` (10 stop-call comparisons), `bus.actual_min_seconds` (-88 signed seconds) and `bus.actual_max_seconds` (289 signed seconds), with `collect_same_day_samples` and `check_early_departure_records` as follow-ups.

Reported usage was 17,513 input / 54 output tokens for `20261022T143808Z-e3red74e` and 17,514 input / 54 output tokens for `20261022T144225Z-x1srsxg5`. Both reported zero cached-input, cache-write-input and reasoning-output tokens.

Recurring permitted acquisition, repeated-day evidence and a completed end-to-end coursework workflow remain pending, along with comparison against existing tools and evidence of actual municipal benefit. Selection usefulness must be compared with a simple deterministic baseline; AI superiority is not established. Invocation/time/size controls are not a proven hard token or monetary budget, which remains open. The offline reports/replay do not complete the agentic coursework assignment.

Earlier funding timeline and source-probe components remain practice exercises; their synthetic tests do not establish live performance or complete a funding workflow.
