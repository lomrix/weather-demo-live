# Hamar Access Lab: exam delivery plan

Planning date: 19 November 2026. Personal work allowance: **20 hours maximum**.
Allocate **16 planned hours and 4 hours of contingency**. The teammate's work
is separate and must be agreed with them; no availability is assumed.

## Submission baseline

Source: `C:/Users/moham/Downloads/project_KIUA_2003.pdf`, the full-semester
**Agentic Workflows for Innlandet** brief, sections 3-4. Earlier two-agent
compulsory-assignment PDFs are different briefs and do not replace this one.

- Written deadline: **3 December 2026, 11:59 AM**, through Wiseflow. Confirm
  current Wiseflow/Canvas information; plan to finish on 2 December.
- English white paper: **7-8 main-text pages**, excluding references and appendices.
- Provided NeurIPS preprint LaTeX format; remove its checklist section.
- Appendices: representative prompt corrections, raw output from one full
  evaluation, and **at least eight meeting reports**.
- Public repository, context files, test set/evaluator and README reproducing
  normal and evaluation runs. Submission commit tagged `exam`, unchanged after
  the deadline. Tagging and publishing need the user's explicit instruction.
- Address the demonstration feedback and any observed failures in the paper.
- Evaluation weights: problem/success criteria 15; harness implementation 30;
  evaluation/stress testing 35; scientific contribution/reflection/compliance 20.

An A is the target, not a promised result. Prioritise evidence against these
criteria while delivering a product people can understand and use.

## Current state and gaps

Existing: walking routes and custom endpoints; fixed driving scenario; B21/B23
stop-access cases; saved journeys and in-app alerts; source-linked Koigen review;
accessibility evidence with explicit gaps; local-model comparisons and failure
records; regression checks and GitHub Actions.

Gaps to close: an understandable interface; one documented source-to-assessment
workflow; consolidated evaluation and two causal fault/repair records; a precise
safe-operation/budget/kill-condition account; independently reviewed source
references; the final white paper and submission package.

The current evidence-extraction patch is uncommitted on
`feature/evidence-linked-notice-extraction`. It has 93-test regression evidence
and browser replay/outage checks. The later small alert `null` fix has a focused
browser check. Close this package before starting another feature branch.

## Delivery blocks: 16 planned personal hours

Dates are target windows, not an expectation to work every day. Work in
bookable blocks around the other exam. Actual time is recorded below.

| Block | Target | Hours | Deliverable and finish condition |
| --- | --- | ---: | --- |
| 0. Establish the release baseline | 19-20 Nov | 0.5 | Review and close the current patch, confirm it is pushed before opening the PR, and choose a last-known-working baseline. Agree the exam's primary user/use-case and check Wiseflow. |
| 1. Usable workspace | 20-23 Nov | 3.5 | A visibly revised map-focused screen with walking/bus/driving choices, relevant controls only, a clear route-impact summary and expandable advanced/evidence content. Verify all three existing mode cases and a narrow-screen layout. |
| 2. Complete the demonstrated workflow | 23-26 Nov | 2.5 | Source review, human-confirmed model, assessment and saved-journey alert work as a documented sequence. Python-owned distances and source/model boundaries stay clear. Demonstrate both normal and unavailable-model paths. |
| 3. Evaluation and safe operation | 26-28 Nov | 2.5 | One repeatable evaluation command and results summary; two complete fault records (input/adversarial source and dependency outage); explicit permissions, secret handling, per-run budget/stop mechanism and human gates. Every claim links to evidence. |
| 4. Final white paper | 28 Nov-1 Dec | 3.5 | Review the teammate's draft against every brief section, insert verified results/architecture/failure analysis, address lecturer feedback, and check the 7-8 page limit and appendices. Explain the full product vision separately from implemented scope. |
| 5. Release rehearsal and hand-in preparation | 2 Dec | 1.5 | Reproduce normal and evaluation commands from a clean checkout; check public access, links and final CI; verify paper/repository consistency and tag the exact submission commit when authorised. |
| Team checkpoints and records | Across the windows | 2.0 | Eight genuine 10-minute check-ins plus approximately five minutes of notes each. Each reviews evidence, makes a decision or resolves a risk, and assigns the next action. |
| **Planned total** | | **16.0** | |
| **Reserved contingency** | | **4.0** | Failed checks, submission problems, essential corrections or scheduling disruption. |

## What counts as finished

**Usability:** someone can identify the selected mode, input/case, assessment
date, normal result and affected result without reading the technical evidence.
Use a short teammate walkthrough with recorded tasks and observed confusion.
The map needs legible routes, endpoints and geographic context. Choose the map
approach early in block 1; bound any dependency investigation to 20 minutes.
Document connectivity/coverage limits rather than silently adding a network dependency.

**Honest mode support:** walking supports the existing From/To selection;
driving is labelled as the fixed supported scenario; bus shows dated service
and stop-access comparisons, with delay unknown. The UI must not offer general
multimodal routing that the backend does not implement.

**Correctness:** known route examples reproduce; out-of-coverage, disconnected,
unreachable, malformed and rejected inputs remain distinct. Accessibility is
not inferred from distance or absent tags. Source facts, model outputs,
source-word rules and hypothetical map inputs remain distinguishable.

**Fault evidence:** each selected fault record contains the exact injected
input/condition, expected and observed outcomes, the stage where the problem
propagates, the mechanism that contains/repairs it, and the regression result.
Synthetic injections and actual model executions are explicitly labelled.

**Budget and stop condition:** specify the actual token/output/request budget
and enforcement mechanism, what is measured after a response, and when no
further calls may start. A request timeout or reported usage alone must not be
described as a proven hard total token/cost limit. Demonstrate a stop/rejection.

**Reproducibility:** retain one complete final evaluation log and its input
versions; CI is green on the published revision; README commands work without
developer-local output folders. Document optional Ollama requirements.

## Work division to agree

**User + coding assistant:** implementation, integration, focused regression
checks, reviewable diffs, screenshots and reproducible evidence artifacts.
The user reviews behavior, understands the main code paths and authorises
commits, pushes and the final release tag.

**Teammate:** independently review the selected source/reference cases;
document actual restrictions, dates and accessibility gaps; provide a limited
comparison with existing services; draft the problem/user/success and
evaluation/reflection sections using the actual saved evidence. Draft the
paper early, before all coding finishes.

**Both:** agree the primary exam narrative, review conclusions, maintain
meeting records, review the full paper and rehearse reproduction. A potential
payer remains a hypothesis unless supported by research or direct evidence.

## Eight meeting records: start now

No existing meeting records have been reported. Arrange eight genuine short
check-ins with the teammate. Suggested windows: 20, 22, 24, 26, 28 and 30
November, then 1 and 2 December; reschedule honestly around availability.
If eight meetings cannot be held, ask the lecturer early about acceptable
records. Do not fabricate or backdate meetings. Retrospective notes from real
dated evidence must be explicitly labelled and their acceptability confirmed.

For each actual meeting, record:

- Date, actual participants and duration.
- Evidence or working feature reviewed (commit, source or result link).
- Decision made and why, including alternatives or rejected agent output.
- Tasks, owner and next checkpoint.

## How each work block runs

1. Select one deliverable from this plan and state its user benefit or exact
   assessment requirement, files affected, finish check and time allowance.
2. Implement a coherent reviewable patch. Show a screenshot for visible work;
   show a reproducible result for technical work.
3. Run relevant checks during editing. Run the full required regression once
   the package is stable, repeating it when changes or failures justify that.
4. Check progress after 10-15 minutes of implementation. Optional research
   that exceeds its allowance is parked; required unresolved work is surfaced.
5. Record actual time, outcome and remaining issue here. Close each package
   with review, commit and a verified push, then create its PR. Group related
   edits into the package. Keep unrelated files out of staging.

Further model sweeps require a specific hypothesis, fixed maximum requests
and a decision they will inform. Existing negative results are already usable
evidence; collecting more results is not itself a completion condition.

## Wider product vision

Retain whole-Hamar coverage, reusable deployment elsewhere, walking/driving/
bus journeys, resident/business/planner workspaces, richer maps including 3D,
recurring reviewed data, consultations, publishing/API access and additional
notification channels as the broader direction. The final paper distinguishes
these opportunities from implemented and verified exam functionality. Scope
extensions consume contingency only after the mandatory submission checks pass.

## Work log

| Date | Block | Actual personal time | Delivered evidence | Remaining issue |
| --- | --- | --- | --- | --- |
| 19 Nov | Planning | To be recorded by user | Brief reviewed; 20-hour limit agreed; meeting-record gap identified | Confirm Wiseflow and agree checkpoint schedule with teammate |
