# Provisional problem and users

Transport staff around Hamar need checkable evidence when investigating recurring road patterns and bus reliability. This direction is provisional; comparison with existing planning tools and municipal usefulness remain unresolved. Earlier weather and funding exercises are preserved, with reproduction instructions in README.md.

# Intended workflow and checkable success

Collect a bounded permitted public-data sample, validate provenance and completeness, analyse observations separately from predictions, then produce a sourced briefing with independently checked claims and explicit unknowns. Future runtime AI requires budget/stop conditions and independent checks. No collection service is started by the offline tasks.

Every reported value must trace to saved source rows and public identifiers. Preserve journey, direction, stop and call-order identities. Reject duplicates and malformed supplied timestamps. Actual comparisons require actual and aimed departure times; predictions remain separate, missing comparisons remain unknown, and cancelled calls are excluded. Independent source-row checks and synthetic failure cases must support conclusions. Do not infer congestion, legal service breach or municipal benefit from the samples.

# As built versus pending

Task 002 generates offline HTML/JSON for three road counters on 20 October 2026, validating 24 contiguous local hours and reporting separate totals, peaks and coverage. Vehicle passages do not measure unique travellers, congestion or bus delay.

Task 003 adds offline HTML/JSON for a filtered Entur B21 snapshot on 21 October 2026. Small-snapshot bus access is demonstrated by the saved successful response; this implementation makes no live requests. It separates source-reported actual departure differences, predictions, unknowns and cancellations. Actual verification is recorded in the task record. The two samples are on different days and are not simultaneous evidence.

Task 004 connects the existing analysis functions into an explicit prepare/replay/codex controller. Every run validates fixtures afresh (never stale generated reports), computes a fact catalogue with source dates/URLs, evidence identifiers and separate input hashes, reads runtime context, and constructs a bounded prompt. AI's intended role is prioritising known finding IDs and permitted follow-up IDs only. A separate program check requires road and bus actual evidence, rejects fabricated/duplicate/unavailable selections and renders only verified values and fixed questions with mandatory caveats and attribution. Trace files record stages, failure reasons, mode, invocation count and reported token usage.

Prepare and clearly synthetic offline replay/rejection paths are verified; they make zero Codex invocations. The real-mode branch is implemented with one saved-login Codex subprocess, a narrowed read-only/no-command-network permission override, event checks, timeout and size limits. Local non-model permission diagnostics were blocked by Access is denied, so permission enforcement, real model behaviour, account access and token reporting remain unverified. No real model call has been run for this task.

Recurring permitted acquisition, repeated-day evidence, a verified real-AI run and a completed end-to-end coursework workflow remain pending, along with comparison against existing tools and evidence of actual municipal benefit. Selection usefulness must be compared with a simple deterministic baseline; AI superiority is not established. Invocation/time/size controls are not a proven hard token or monetary budget, which remains open. The offline reports/replay do not complete the agentic coursework assignment.

Earlier funding timeline and source-probe components remain practice exercises; their synthetic tests do not establish live performance or complete a funding workflow.
