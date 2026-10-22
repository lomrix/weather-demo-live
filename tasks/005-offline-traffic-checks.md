# Task 005: repeatable offline traffic checks

Implemented 22 October 2026 within five tracked files: `scripts/verify_traffic.py`, `.github/workflows/traffic-offline.yml`, this record, `README.md` and `docs/prompt-log.md`. Existing application/controller, schema, context, eval, fixtures and permissions are unchanged. Pre-existing `docs/problem-candidates.md` changes and `.codex/` are untouched.

The standard-library verifier resolves repository paths from its own file and invokes only prepare/synthetic replay with `sys.executable`, `shell=False`, explicit UTF-8 capture, no source bytecode writes and a 30-second timeout per invocation. Evidence is unique under ignored `out/traffic-verification/`; existing runs are preserved. Each case records command arguments, stdout/stderr, actual controller exit, exact validated run directory, assertions and status, including failures. Expected rejection is a passing test; unexpected results make the final command fail nonzero. No prior out/ artifact is required.

Independent expectations cover all ten reviewed anchors, dates, URLs, input-byte SHA256 hashes and separate original bus response hash; context hash, fixed follow-up, source-row evidence IDs, provider attribution, six mandatory limitations and representative HTML content. Every controller trace must have zero Codex invocations and null usage. Rejections require useful failure reasons, failed traces, correct stages and no final briefing. Missing actuals stay null rather than becoming zero delay; predictions remain separate. Content assertions are not visual/accessibility inspection.

## Local evidence

Platform: Windows 11 (`Windows-11-10.0.26300-SP0`), Python 3.12.12. Command from repository root:

```text
python scripts/verify_traffic.py
```

First run exited **0**, stderr empty. stdout:

```text
EVIDENCE_DIRECTORY C:\Users\moham\weather-demo-live\out\traffic-verification\checks-im6sw61n
PASS prepare (controller exit 0)
PASS valid-replay (controller exit 0)
PASS unknown-highlight (controller exit 1)
PASS duplicate-highlights (controller exit 1)
PASS duplicate-followups (controller exit 1)
PASS malformed-time (controller exit 1)
PASS missing-input (controller exit 1)
PASS no-actuals-prepare (controller exit 0)
PASS unavailable-actual (controller exit 1)
PASS: 9/9 offline cases; zero model requests
```

Machine-readable commands, captured outputs, run paths and assertion results: `out/traffic-verification/checks-im6sw61n/summary.json` and per-case result JSON files. The malformed timestamp failed before `inputs_validated`. Duplicate highlights retained both road and bus categories, ensuring duplicate rejection was tested. Boundary preparation verified actual_count 0, null min/max and prediction_only_count 8; unavailable-statistic replay failed without a briefing. All nine controller traces recorded zero model invocations and null token usage. These are synthetic decisions applied to saved real data and mutated copies, not live experiments.

After removing an unused verifier variable, the same command was rerun: exit **0**, stderr empty, the same nine PASS case lines and final `PASS: 9/9 offline cases; zero model requests`. Its evidence directory is `out/traffic-verification/checks-v6hz0xjk/`, with complete results in `summary.json`. This second fresh run also confirms independence from earlier out/ results. `git diff --check` exited **0**, no output. Status review showed only the five allowed task files added/modified by this task, alongside the pre-existing unrelated `docs/problem-candidates.md` and `.codex/`. No funding code changed; unrelated funding regression tests were not run.

## GitHub status and limits

Workflow: PRs targeting main, pushes to main and manual dispatch; read-only contents permission, checkout without persisted credentials, Python 3.12, Ubuntu/Windows matrix with fail-fast false, five-minute job timeout and UTF-8/no-bytecode environment. Uses official `actions/checkout@v7` and `actions/setup-python@v7` as specified by the brief's dated upstream README verification. No network requests were made to re-verify upstream during this task. No path filters, installs, credentials/model setup or scheduled acquisition. GitHub action/runtime setup normally downloads components; this is not a runner network sandbox.

GitHub execution and Linux verification remain **pending** until remote runs occur. No observed remote red-then-green evidence exists from this task. Recurring collection, usefulness comparison against a deterministic baseline, a hard token/cost budget, municipal benefit and full coursework completion remain pending. No model calls, live-data requests, package installation, commits or pushes were performed.
