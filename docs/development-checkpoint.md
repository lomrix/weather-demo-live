# Development checkpoint — 25 November 2026

## Completed and merged

PR #32 was merged as `28527ac`; the feature branch was deleted remotely.
The merged files matched tested commit `53e80ac`. PR and post-merge Ubuntu and
Windows checks passed. A clean-copy run passed 230 tests, saved-data verifiers
and 14/14 frozen journey cases. Original failures and repairs are preserved.

## Current local follow-up

Branch: `feature/phone-review-walkthrough`. The user authorised one bounded
save-and-commit step before stopping for the day. This follow-up adds a direct
expandable View stops list beside the bus result, English/Norwegian labels,
a 44 px summary target and bounded list scrolling. A 390 × 844 browser check
covered B22's 39 stops, keyboard access and dark mode, without horizontal page
overflow or observed JavaScript errors. Seventeen focused bus/static checks,
JavaScript syntax and whitespace checks passed. It is not yet pushed or merged.
The professor task sheet and blank observation record are in
`docs/phone-review-walkthrough.md`. Developer checks are not a user study.

## Resume next time

1. Publish this saved follow-up through a PR and check CI before merging.
2. Review the Overleaf draft against implemented features and preserved results.
   That report-to-evidence review has not been completed in this stopping step.
3. Obtain the teammate's actual experiment code, model settings and raw logs.
4. Record an independent phone walkthrough; the observation sheet is still blank.
5. Ask the professor on 26 November about missing meeting reports. No answer
   has been received; never fabricate past meetings or human observations.
6. Align the final paper/appendices and rehearse the exact submission version.
   Create the immutable exam tag only when explicitly authorised.

## Running and sharing

Normal start: `python hamar_workspace.py --open`. The temporary shared preview
was checked on 25 November, with shutdown scheduled for 26 November at 17:00
Europe/Oslo. Its current URL/process information is kept in the local ChatGPT
mirror's `.hamar-build/shared-preview.json`. Recheck it before reuse: the laptop
must stay awake and online, and the sharing session must remain running.
VS Code is not required. Local AI is disabled in that public preview.

Keep unrelated/deferred items out of the follow-up commit: `.codex/`,
`.python-version`, `hosted_preview.py`, `check_hosted_preview.py`,
`docs/hosted-preview.md`, `hamar-compulsory-2-draft.pdf`.

The user has limited daily usage and wants a completed stopping point, not a
new long-running task. No grade, paid demand, complete physical access coverage,
meeting evidence or unshared teammate result should be claimed as established.
