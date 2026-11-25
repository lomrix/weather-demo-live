# Exam readiness — 25 November 2026

This package improves the usable product and makes its claims reproducible. It
does not certify an A grade, physical accessibility or willingness to pay.

## Delivered product changes

- A phone-first map with a separate journey-planning sheet, larger controls,
  English/Norwegian and light/dark preferences; desktop planning remains available.
- House-number search uses the official Kartverket service across Hamar 3403.
  The municipal snapshot also supplies 564 offline road/path names. This replaces
  reliance on a small list of demonstration places. Online address lookup and
  saved-network routing are separate dependencies.
- Default walking uses 82,295 mapped links and starts without invented works.
  Historical closure, bus-access and driving examples remain reproducible.
- Municipal endpoints project onto existing walking links. The summary discloses
  start/destination access offsets separately; those unverified connections are
  excluded from the network distance. A route is not a door-to-door guarantee.
- Details contains an AI pause/resume control. It blocks new requests, including
  server-side requests; manual route calculations remain available. It does not
  guarantee cancellation of computation already running in Ollama.

## Reproduce

From the repository root, using Python's standard library:

```text
python hamar_workspace.py --open
python -B -m harness.run_readiness --output out/my-new-readiness-run
python -B -m unittest check_readiness check_notice_evidence check_ollama_scenario -v
```

Choose a new output directory so previous results are retained. The full named
suite takes several minutes. Its data/model checks are offline; no new model
experiment is claimed. CI runs this command on Windows and Ubuntu and retains
logs as artifacts. Remote CI and clean-checkout rehearsal remain to be checked
after publication; a local pass is not a remote CI result.

## Preserved results and interpretation

See `fixtures/evaluation/runs/2026-11-25-readiness/` for the complete regression
log, saved-data checks, journey results, final focused safety log and evidence
manifest. The full run passed **228 tests**. After the last default-transport
redirect guard and its extra test, **48 focused tests** passed. After removing a duplicate, unreachable street-search handler, **59 final focused tests** passed. These are distinct runs, not a claim that a final 229-test full run was executed.

`fixtures/evaluation/municipal-journeys.json` froze 14 source-backed and rejection
cases before the first validation. They span central, suburban, rural and
northern locations. The before/after folders retain **13/14 then 14/14** results.
Eleven cases produce routes; the others intentionally reject or identify equal
endpoints. An independent distance-only Dijkstra checks the returned network
path and weight. This tests graph/software consistency, not independent street
survey truth. Resolver timings exclude browser, online search and human work.

### Fault record 1: distinct addresses collapsed to one vertex

The frozen neighbouring-address case failed with nearest-vertex snapping: two
different coordinates selected the same vertex and returned `same_place`.
Request-local edge projection now splits the existing link, retaining direction
and closure handling without joining nearby parallel roads. The corrected
mapped segment measures 4 m; approximately 8 m access offsets at each endpoint
are separately excluded and unverified. Synthetic checks cover one-way travel,
parallel roads, base-graph immutability and closure handling. This is a causal
software repair, not evidence that this is a safe four-metre real-world walk.

### Fault record 2: address dependency unavailable

The address adapter's unavailable/timeout responses are tested separately from
zero matches. Browser verification simulates an unavailable address response:
saved named streets remain searchable, and map/saved-place planning remains
available. This is containment of a simulated dependency failure, not a claim
that Kartverket actually went down. Earlier saved model-outage tests likewise
must retain their simulated labels.

## Local AI limits and review gates

`harness/model_budget.py` enforces one request per action, no automatic retries,
a fixed loopback POST endpoint, no redirects, 12 KiB prompt and 16 KiB response
caps. Requests configure a 4,096-token context and at most 700 generated tokens
(the smaller caller limit is retained). Ollama enforces those token settings;
Python rejects reported usage overruns. Missing usage is not proof of measured
token compliance. Size/time controls do not establish a monetary cap or a hard
end-to-end execution deadline. No new live-model comparison was run here, and
the historical extraction experiment is preserved with its original settings.

Source text is untrusted input. Draft claims require review and cannot silently
become verified closures. Koigen's unknown dates/geometry remain unknown; model
dates and a user-confirmed simulation remain labelled as such. Python computes
distances; the LLM does not supply authoritative route lengths. The broader
platform and potential users/payers belong in the report's future-work section,
alongside evidence needed to establish usefulness, rather than paid-demand claims.

## Human evidence still required

The user will ask the professor tomorrow about the meeting-report requirement.
Record the answer and genuine available evidence; do not manufacture past
meetings. The teammate's Overleaf draft is substantial work, but unpublished
patches and experiment claims require the actual scripts, source/reference
versions, model digests/options and raw outputs before being reported as verified.
Keep incomplete metadata explicit rather than recreating it after the fact.

Run a short independent walkthrough before submission. Use anonymous P1/P2 labels
and public landmarks, without names or home/work addresses. Ask each person to:

1. Plan a walk between two public places on a phone, without coaching.
2. Identify distance, excluded access offsets and whether any closure is real
   or simulated. Record their interpretation before explaining the interface.
3. Find a bus line and its ordered stops; distinguish saved data from live service.
4. Interpret a source-backed notice and a hypothetical impact; record errors,
   hints needed, completion time and one improvement suggestion.

Record browser/device, task, observed outcome, mistakes and intervention. Leave
the record blank until someone actually performs it. A developer's automated
browser test is not a user study. Then align the paper's numerical claims with
the preserved evidence, review the required appendices, rehearse from a clean
checkout and create the final immutable submission tag only when authorised.
