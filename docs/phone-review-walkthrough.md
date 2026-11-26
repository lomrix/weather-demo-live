# Phone review walkthrough — 25 November 2026

## Current technical evidence

PR #32 merged as `28527ac`; its Ubuntu and Windows post-merge checks both passed.
A developer-operated browser walkthrough at 390 × 844 checked the merged app:

- From/To search returned the saved Seminargata and Torggata streets and live
  Kartverket address choices. Selecting the street representatives produced a
  48 m network route, with zero access offsets. Street representatives are not
  whole-street routes or a statement about any person's home.
- B22's first saved route variant displayed 39 ordered stops, 26 inside Hamar,
  and 34 scheduled journeys on the snapshot date, 19 November 2026. The screen
  explicitly distinguished this from live departures and closure assessment.
- The Koigen example required confirmation and retained the modeled 323 m to
  593 m comparison (+270 m), with dates/extent unknown.
- No JavaScript errors were observed in the inspected browser error log.

The walkthrough found a usability issue: viewing stops required reopening the
bus planner. A small follow-up adds a native expandable **View stops** list
beside the route result. It was checked with all 39 B22 stops, English/Norwegian,
keyboard Enter, a 44 px control height and dark mode. At 390 px viewport width,
the document width was 375 px, with no horizontal page overflow. This patch is
local on `feature/phone-review-walkthrough`; it is not part of the merged PR #32.
These observations are developer verification, not a human usability study or
proof of commercial demand. Phone emulation does not replace a physical-phone test.

Focused verification: `python -B -m unittest check_bus_catalogue check_workspace.StaticAssetTests -v` passed 17 tests. JavaScript syntax and Git whitespace checks passed. No backend changes were made in this follow-up.

## Arrange the review

Allow about 15 minutes on the reviewer's own phone/browser. For a temporary
sharing link, the host laptop, Python server and sharing process must stay on
and online. Check the actual link immediately before the agreed session. Do
not send the reviewer a localhost URL or an old expired sharing URL. No login
or personal home/work address should be necessary.

First let the reviewer try without hints. Record where a hint is needed, then
allow it so the review can continue. Prefer public destinations. Explain that
this is a planning prototype; do not ask the person to follow an unverified
route physically.

## Reviewer tasks

1. Plan a walk between two public places or streets in Hamar. Explain where
   you would start and finish, what distance is shown and what it excludes.
2. Find bus B22, choose a route variant and find its ordered stops. Explain
   whether these are live departures or saved timetable data.
3. Load the Koigen example, read the source-scope explanation, and assess it
   after reviewing the modeled-section confirmation. Explain what comes from
   the notice, what is hypothetical, and how the route changes.
4. Change to Norwegian or English. Identify the most confusing part and one
   change that would make the tool more useful in practice.

Ask afterwards: Who would benefit from this? What would they currently do
instead? What evidence or capability is missing before they would rely on it?
Treat answers as feedback, not proof that somebody would pay.

## Observation record — not completed yet

Use anonymous P1/P2 labels, without names or identifying locations.

| Item | Record after the actual review |
| --- | --- |
| Date, anonymous participant, phone/browser | Pending |
| Walk: completed unaided / hints / blocked; time | Pending |
| Bus: completed unaided / hints / blocked; time | Pending |
| Closure: understood facts, simulation and unknowns | Pending |
| First point of confusion / exact wording if permitted | Pending |
| Most useful capability / most important missing capability | Pending |
| Resulting change and verification | Pending |

Separately ask the professor about the meeting-report requirement on
26 November. Record the guidance accurately; do not reconstruct meetings that
did not happen. Teammate experiment claims still need the actual scripts,
model settings, references and raw outputs before being treated as verified.
