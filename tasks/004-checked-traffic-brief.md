# Task 004: checked traffic briefing

Purpose: connect saved genuine road/bus analysis into a checkable briefing for human review. Reuses `traffic_report.analyse` and `bus_timing_report.analyse` without modifying existing modules/fixtures or reading old reports. Six permitted files only: controller, runtime context, strict output schema, this record, README and SPEC.

## Architecture and acceptance

Explicit prepare/replay/codex modes; a unique out/traffic-brief directory and trace per run. Validated inputs produce ten computed fact IDs with dates, units, source links, evidence identifiers and separate input-file hashes. Bus original-whole-response hash remains separately labelled. Runtime context is actually read and hashed. Prompt contains fixed instructions, computed numeric facts and permitted questions, never raw response/repository/environment text. Missing actual statistics remain null.

Independent checks enforce exactly two keys, 2?4 distinct known available highlights including road and bus actual evidence, and 1?2 distinct permitted follow-ups. Only catalogue facts/fixed questions enter rendered HTML/JSON; mandatory limitations and provider attribution are code-enforced. Replay is explicitly synthetic, not real AI execution. Prepare makes no final briefing. Rejections record failure reasons and do not produce final briefings or relabel older runs as current.

Real-mode branch resolves existing codex.exe without changing models or inspecting login files. It uses shell=False, stdin prompt, --json, --ephemeral, --strict-config, --output-schema and -o. One invocation, no controller retries, 12,000 prompt characters, 120-second child timeout, 4,096 draft bytes and 1 MiB per stdout/stderr capture. On timeout/cancellation the created child tree is targeted for termination. JSONL rejects command_execution/file_change/mcp_tool_call/web_search items and error/failed turns; requires process exit zero, completed turn and checked decision. Reported usage is recorded, otherwise null. Event checks are acceptance controls, not proof that no tool began. Time/size/invocation controls are not a proven hard token or monetary budget.

## Final offline verification, 21 October 2026

The following commands were launched by a standard-library verification here-string piped to `python -`. That wrapper exited **0**, checked traces, all ten anchors, context hash, source dates/input hashes, replay values/citations/evidence/caveats/attribution and no final files on prepare/rejection. It also compiled the controller in memory without bytecode writes. Exact machine-readable outputs are retained in `out/task004-checks-domzmx58/final-results.json`.

```text
python harness/traffic_brief.py --mode prepare
```

Exit **0**. stdout:

```text
RUN_DIRECTORY C:\Users\moham\weather-demo-live\out\traffic-brief\20261021T145932Z-8yujdxlp
PREPARED; zero Codex invocations; no final briefing
```

stderr:

```text
(empty)
```

```text
python harness/traffic_brief.py --mode replay --decision-file C:\Users\moham\weather-demo-live\out\task004-checks-domzmx58\valid.json
```

Exit **0**. stdout:

```text
RUN_DIRECTORY C:\Users\moham\weather-demo-live\out\traffic-brief\20261021T145933Z-6pvah8dn
OFFLINE REPLAY - synthetic decision; not real AI execution; generated C:\Users\moham\weather-demo-live\out\traffic-brief\20261021T145933Z-6pvah8dn\briefing.json and C:\Users\moham\weather-demo-live\out\traffic-brief\20261021T145933Z-6pvah8dn\briefing.html
```

stderr:

```text
(empty)
```

```text
python harness/traffic_brief.py --mode replay --decision-file C:\Users\moham\weather-demo-live\out\task004-checks-domzmx58\invalid.json
```

Exit **1**. stdout:

```text
RUN_DIRECTORY C:\Users\moham\weather-demo-live\out\traffic-brief\20261021T145933Z-oqv8qh8k
```

stderr:

```text
FAILED: Duplicate or unknown highlight_ids; no successful current briefing; older runs may be stale.
```

```text
python harness/traffic_brief.py --mode prepare --bus-input C:\Users\moham\weather-demo-live\out\task004-checks-domzmx58\bad-bus.json
```

Exit **1**. stdout:

```text
RUN_DIRECTORY C:\Users\moham\weather-demo-live\out\traffic-brief\20261021T145933Z-xdlhohx4
```

stderr:

```text
FAILED: Malformed timestamp: 'not-a-date'; no successful current briefing; older runs may be stale.
```

All four final runs recorded **zero Codex invocations**. Prepare saved prompt/facts/trace and no briefing. Valid replay selected bus.actual_max_seconds = 289 signed seconds and road.vang_kirke.peak = 1834 vehicle passages in the peak hour, with collect_same_day_samples. Both rejection runs had no final briefing; malformed bus input failed before the inputs_validated stage.

Computed and independently asserted anchors: road totals/peaks Vang kirke 19576/1834, Disen ?st 19806/1831, Vangsvegen 91 13976/1149; bus actual_count 10, prediction_only_count 8, actual_min_seconds -88, actual_max_seconds 289. Dates retained: road 2026-10-20, bus 2026-10-21. Input SHA256 values were recomputed from fixture bytes and compared with facts.json, separately from the bus original-response hash. The context-file hash was independently compared with trace.json. HTML content assertions are not visual inspection.

Eight additional direct decision-validator checks rejected extra keys, road-only selection, bus-only selection, duplicate highlights, wrong array type, unknown follow-up, duplicate follow-ups and a null-statistic highlight. Executed in an offline `python -` wrapper, exit **0**, stdout: `Eight additional direct decision-rejection checks: OK (offline; zero model invocations)`.

## CLI diagnostic and blocked verification

Read-only commands `codex.exe exec --help; codex.exe debug --help` exited **0**, and `codex.exe debug prompt-input --help` exited **0**. They showed available flags and temporary-path Access is denied warnings; no model requests.

A separate non-model configuration diagnostic used Python subprocess.run(shell=False) with this argument list:

```json
[
  "codex.exe",
  "debug",
  "prompt-input",
  "-c",
  "permissions.traffic-brief={filesystem={\":minimal\"=\"read\",\":workspace_roots\"={\".\"=\"read\",\".env\"=\"deny\",\".env.local\"=\"deny\"}},network={enabled=false}}",
  "-c",
  "default_permissions=\"traffic-brief\"",
  "Offline permission syntax diagnostic only."
]
```

Exit **1**. stderr included warnings that stale arg0 directories could not be cleaned and PATH aliases could not be created, followed by `Error: Access is denied. (os error 5)`. stdout/stderr are retained as `out/task004-checks-domzmx58/permission-diagnostic.stdout` and `.stderr`; no model was invoked. Syntax and actual permission enforcement could not be verified in this environment. No escalation or permission change was attempted. Real Codex mode was not run, as requested; account availability, managed/local profile compatibility, real event shape/token reporting, process-tree controls and actual end-to-end AI behaviour remain unverified.

The first verification wrapper exited **1** due to a Windows cp1252-versus-UTF-8 decoding error while capturing replay stdout, not input validation. Re-running with correct decoding completed all checks; final console labels use ASCII and a final rerun passed. Earlier run directories/temporary synthetic inputs are preserved under out/. No existing files were moved/deleted.

## Limits and next steps

`git diff --check` exited **0**, no output. `git status --short; git diff --stat` exited **0**, showing README.md and SPEC.md modified plus the new context/controller/task files and pre-existing untracked `.codex/`. `rg --files context` listed only the two permitted context files; the explicit git diff for AGENTS.md, both earlier analysis modules and both fixtures was empty (command exit **0**).

No source-network or real AI requests, secret reads, package installation, eval edits, permission-file changes, commits or pushes. No unrelated funding tests were run. HTML visual inspection remains pending. After review and permission compatibility verification, the student can run `python harness/traffic_brief.py --mode codex` in an ordinary terminal to establish real behaviour. Recurring acquisition, repeated-day evidence, deterministic-baseline comparison, a proven hard token/monetary budget and demonstrated municipal benefit remain pending. This is not a completed coursework submission or proven municipal service.
