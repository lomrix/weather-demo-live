# Provisional problem and users

Transport staff around Hamar need checkable evidence when investigating recurring road patterns and bus reliability. This direction is provisional; comparison with existing planning tools and municipal usefulness remain unresolved. The earlier funding exercise is preserved, with reproduction instructions in README.md; the earlier weather exercise files were removed and remain only in Git history.

# Intended workflow and checkable success

Collect a bounded permitted public-data sample, validate provenance and completeness, analyse observations separately from predictions, then produce a sourced briefing with independently checked claims and explicit unknowns. Future runtime AI requires budget/stop conditions and independent checks. No collection service is started by the offline tasks.

Every reported value must trace to saved source rows and public identifiers. Preserve journey, direction, stop and call-order identities. Reject duplicates and malformed supplied timestamps. Actual comparisons require actual and aimed departure times; predictions remain separate, missing comparisons remain unknown, and cancelled calls are excluded. Independent source-row checks and synthetic failure cases must support conclusions. Do not infer congestion, legal service breach or municipal benefit from the samples.

# Exam priorities and future vision

The exam delivery prioritizes a connected, demonstrable workflow from source
review and explicit confirmation through route assessment and saved-journey
alerts; demonstrated walking, driving and bus-access modes; and a usable UI.
Measure the AI contribution against a non-AI baseline, with request counts,
usage and limitations rather than an unsupported superiority claim. Provide
accessibility evidence with unknowns made explicit, and reproducible failure
experiments that distinguish synthetic checks from live results. These are
priorities, not claims that all evidence has been completed.

The wider vision of recurring public-data acquisition, broader geographic and
transport coverage, continuous monitoring and additional notification
channels remains future work, subject to provenance, privacy and operational
checks.

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

# Saved journeys and source-backed alerts

Add named saved journeys as a later extension of the existing notice-to-map
workflow. A saved journey stores the existing case, journey or user-selected
endpoints, and the mapped mode; it does not store a person's identity, contact
details or a continuous location. A person can review which saved journeys
could be affected when a notice is checked.

Start alert delivery in the browser workspace. A source-backed in-app alert may
cover:

- upcoming works that have a stated future period;
- a source change affecting a route, closure segment or saved journey;
- an extended end date or changed works period; and
- a confirmed reopening of an affected route.

Every alert must show the saved source, the supporting excerpt or extracted
source fact, and the `last_checked` time. It must link to the saved notice or
official source and state whether the information is scheduled, announced,
unchanged, or confirmed. Rechecking may refresh `last_checked` without creating
a duplicate alert when the source fact is unchanged.

Keep **scheduled completion** separate from **verified reopening**. A planning
date, stated end date or project timetable is a scheduled completion only. Do
not label access restored or reopened until the source explicitly confirms the
reopening or provides separately verified observation evidence. Parking,
project-milestone and publication dates must not be reused as footpath closure
or reopening dates.

Email and phone notifications are later delivery extensions. They require an
explicit separate opt-in, a contact-address design, delivery-failure handling,
retention/deletion controls and a review of personal-data scope; none are part
of the initial in-app alert workflow.

Source checks must remain bounded and inspectable. The first implementation
may use saved notices and explicit user-triggered checks; it must not imply
continuous monitoring. Alert matching must reuse the checked notice review
and Python-owned map/routing logic rather than allowing an AI draft to change
journey geometry or declare reopening.

# Citywide notifications and Hamar bus-service coverage

These are explicit product requirements. Existing saved-journey simulations
and the B21/B23 fixtures are demonstrations, not completion of this scope.

## Notifications people can follow

Provide a visible notification centre, with two independently selectable scopes:

- Hamar-area updates: follow new works and announced restrictions even without
  saving a journey. Later filters include area, transport mode and bus line.
- My journeys: identify which saved journeys are affected, showing a calculated
  consequence only when the relevant geometry and routing mode are supported.

Represent announced/upcoming works, reported work starts, announced/active
closures, changed or extended dates, and explicitly confirmed reopening.
Construction starting does not itself prove a road is closed. Completing a
construction project does not itself prove every access restriction is lifted.
An elapsed planned end date means reopening is unconfirmed until the source
confirms access restoration. An unavailable source is not a reopening event.

Each notification retains source URL, supporting evidence, source-check time,
event status, relevant location/mode, and whether its impact is modeled.
Users can mark read, dismiss, restore, and manage what they follow. Stable event
identities and source revisions prevent duplicates and distinguish genuine
changes from repeated checks. Synthetic examples remain separately labeled.

Delivery while the app is open and push delivery while it is closed are
different capabilities. Background delivery requires a deployed recurring
source checker, persisted subscriptions and an opt-in push delivery service;
browser-local storage and refresh alone do not provide it. Do not claim it
exists until tested on a subscribed device with the app closed. Obtain browser
notification consent only after an explicit user action; denied permission
must preserve the in-app notification centre. Store no personal contact details
or continuous location in the present prototype.

Verification must cover a new notice, upcoming-to-active update, date extension,
confirmed reopening, expired but unconfirmed reopening, missing source,
unchanged refresh, dismissal persistence, and an unrelated saved journey.
Citywide notices must remain viewable without claiming that all works are known.

## All bus services serving Hamar

Import an official Entur timetable dataset instead of manually adding one
fixture per line. Discover every bus line serving stops in the declared Hamar
area; retain stable line, direction, journey-pattern, trip and quay identities.
Keep the complete relevant stop sequences, including portions outside Hamar.
Preserve calendars and date exceptions so an unavailable departure is never
presented as running on the selected day. Distinguish scheduled from real-time
information and retain the feed version, retrieval time, hashes and attribution.

The intended geographic scope is Hamar, not just the current study rectangle.
Publish the exact area definition used for discovery and any gaps. Do not label
an inventory complete until checked against the chosen official source. A route
catalogue, scheduled journey lookup, pedestrian access assessment, bus-road
diversion and delay prediction are separate coverage claims. In particular,
importing a line must not imply that its outside-map stops are walk-assessable,
or that a pedestrian detour calculates bus driving time or delay.

Acceptance includes a source-backed searchable line catalogue, direction and
date selection, ordered stops for imported trips, explicit no-service outcomes,
reproducible imports and gap reporting. B21/B23 remain regression examples for
the common assessment path rather than special-case code. Reconcile the
catalogue with its official input before claiming all Hamar services are covered.

Official starting points:
- https://www.hamar.kommune.no/veger-og-gater/trafikkmeldinger/
- https://developer.entur.no/open-data/timetable
- https://developer.entur.no/apis/graphql/journey-planner/query/stopPlacesByBbox
- https://developer.entur.no/open-data/realtime

The municipal traffic page links to municipal closures, county/national road
information and Innlandstrafikk bus updates. A single municipal article feed
does not establish comprehensive coverage of all these authorities.
