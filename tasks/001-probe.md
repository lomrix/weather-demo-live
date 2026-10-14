# Task 001: Probe the saved funding-rule excerpt

## Goal

This is an offline probe of a saved excerpt. Read the saved public-rule excerpt and produce a checkable JSON record without interpreting the funding requirement.

## Context

- Input: `fixtures/funding-timeline-rule.json`
- Planned implementation: `harness/probe.py`
- Planned checker: `eval/check_probe.py`
- Output: `out/probe.json`

## Constraints

- Python standard library only.
- No network requests, AI calls or identifying personal data.
- Do not change the fixture or existing application.
- Never edit `eval/` without explicit human permission.
- Read values from the input; do not hard-code its contents.

## Acceptance

These acceptance criteria are proposed and await human review.

- Output has `source_url` and `checked_on` copied from the input.
- Output has exactly one item containing the input's `rule_id` and `source_quote`, unchanged.
- Missing or malformed input fails clearly.
- The independent check must fail before implementation.
- From the repository root, run these separately:

  ```text
  python harness/probe.py
  ```

  ```text
  python eval/check_probe.py
  ```

- The checker prints `PASS` only when all its checks pass.

## Out of scope

Live fetching, rule interpretation, eligibility decisions, the website and the full AI workflow.
