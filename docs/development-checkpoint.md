# Development checkpoint — 25 November 2026

Branch: `feature/mobile-map-workspace`. The user authorised saving and committing
the mobile, municipality-wide address/routing and readiness package. Publication
has not been authorised. The last merged PR reported by the user is #31.

The current product changes, exact checks and pending human evidence are indexed
in [exam-readiness.md](exam-readiness.md). Results: 228 full regression tests,
59 final focused address/safety tests, and 14/14 frozen graph cases after repairing
nearby-address snapping (13/14 before). These are separate, correctly scoped runs.
Browser checks use replayed public address points and simulated source failure;
they do not constitute a human usability study or new live-model experiment.

Next: review the preserved evidence, obtain the professor's meeting-report
guidance tomorrow, get the teammate's actual experiment patches/logs, complete
an independent walkthrough, align the final paper, and rehearse a clean checkout.
No meeting, experiment, grade, payment demand or physical access claim is invented.

Start with `python hamar_workspace.py --open`; restart any older Python server.
Temporary sharing links require a running host and may expire.

Keep these unrelated/deferred items out of this feature commit: `.codex/`,
`.python-version`, `hosted_preview.py`, `check_hosted_preview.py`,
`docs/hosted-preview.md`, `hamar-compulsory-2-draft.pdf`.

The user wants broad Hamar usefulness and a polished phone experience. Continue
with coherent, visible patches and proportionate checks. Do not push or create
the final submission tag without authorisation. Do not edit `eval/`.
