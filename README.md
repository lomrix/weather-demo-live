# Hamar traffic and bus reliability - provisional project

Intended users are transport staff reviewing recurring road patterns and bus timing evidence around Hamar. These standard-library components use genuine saved samples offline. The checked briefing controller has two successful real AI runs using saved real data; recurring collection remains pending.

## Hamar Access Lab

Hamar Access Lab is the current integration for lecturer and teammate review.
It demonstrates a bounded, offline walking-access workflow around Hamar:
import a sanitized OpenStreetMap walking graph, compare a baseline with a
fixed hypothetical interruption, render an inspectable map, and optionally
compare Python-owned mitigation candidates through a local Ollama model.
The workflow is evidence-led and does not claim accessibility, legal access,
recurring performance, causation or intervention success.

The two demonstrated real-data cases are:

* **Ringgata junction area to Ankerskogen:** 1,384 m baseline; the confirmed
  seven-segment hypothetical interruption yields a 2,332 m closure-only
  detour (+948 m).
* **Furubergvegen-Måsåbekkvegen junction:** two mapped journeys with 201 m
  and 241 m baselines; closure-only routes are 362 m and 402 m.

The repository uses Python's standard library only. Use Python 3.12 or newer,
with no package installation required for the offline workflow. The saved OSM
fixtures preserve OpenStreetMap attribution and ODbL provenance while removing
contributor account metadata and personal contact tags. Their reproducible
sanitization procedure and separate original-download/submitted-fixture
checksums are in [fixtures/maps/README.md](fixtures/maps/README.md) and
[fixtures/maps/manifest.json](fixtures/maps/manifest.json).

Run the offline browser demo from the repository root:

```text
python harness\render_comparison.py --output out\hamar-comparison.html < fixtures\comparisons\synthetic-comparison-qwen2.5-3b.json
```

For PowerShell or other environments without shell input redirection, use:

```text
python -c "import subprocess,sys; from pathlib import Path; p=Path(r'fixtures/comparisons/synthetic-comparison-qwen2.5-3b.json'); subprocess.run([sys.executable, r'harness/render_comparison.py', '--output', r'out/hamar-comparison.html'], input=p.read_bytes(), check=True)"
```

Run the five deterministic integration suites:

```text
python -m unittest check_ringgata_demo.py check_hamar_real_case.py check_ollama_scenario.py check_comparison_renderer.py check_scenario_compare.py -v
```

The GitHub Actions workflow runs that same command on Ubuntu and Windows,
alongside the existing saved traffic, route-coverage and bounded-bus
verifiers. These checks are offline and synthetic where stated; they do not
constitute a live model evaluation or a visual/accessibility inspection.

The optional live path uses a local Ollama installation:

```text
ollama pull qwen2.5:3b
python harness\ollama_scenario.py --scenario fixtures\scenarios\hamar-ringgata-ankerskogen.json --closure-mode walking --closure-links osm-way-1396077789-segment-7 osm-way-1396077789-segment-8 osm-way-1396077789-segment-9 osm-way-1396077789-segment-10 osm-way-1396077789-segment-11 osm-way-1396077789-segment-12 osm-way-1396077789-segment-13 --compare-options --question "Compare two hypothetical pedestrian mitigations for the confirmed crossing closure."
```

The live command is opt-in and contacts only the local Ollama endpoint. The
model selects candidate IDs and reasons; route geometry, assumed lengths and
the confirmed closure remain Python-controlled. Candidate connections require
site checks for surface, access, safety and accessibility.

The Ringgata notice checker and saved notice evidence were copied from Kai's
upstream integration at commit `b97988e`, specifically the checker, input
snapshot and saved run used by the replay. The evidence is minimal and
attributed to Hamar municipality, but no general reuse licence has been
verified; redistribution permission remains pending confirmation from Kai.

## Ringgata offline integration

Run the checked Ringgata replay from the repository root:

```text
python ringgata_demo.py
python ringgata_demo.py --json | python harness/render_ringgata.py --output out/ringgata.html
python -m unittest check_ringgata_demo.py -v
```

The normal replay exits 0 and reports the illustrative 800 m baseline, 1,050 m hypothetical crossing-closed route and +250 m change, plus the saved Entur totals of 26 calls, 13 actual and 13 prediction-only. The renderer requires an explicit output path. A valid baseline whose specified crossing disconnects the destination exits 0 and renders `No route available`; a disconnected baseline, wrong notice location or missing bus fixture stops with a nonzero exit. Failed or empty renderer input does not create or modify the requested HTML file.

The notice checker and saved notice evidence were copied from Kai's upstream integration at commit `b97988e`, specifically the checker, input snapshot and saved run used by the replay. Redistribution is pending confirmation from Kai. The Entur fixture and route analyzer are saved transport-repository components with the fixture's NLOD attribution; the sample's geographic connection to Ringgata remains unverified. Notice excerpts are minimal and linked to the official Hamar municipality notice.

## Offline scenario comparison

The reusable comparison engine accepts a saved JSON scenario, so a future Ollama agent can propose alternatives without changing Python:

```text
python -m unittest check_scenario_compare.py -v
python -c "import json; from harness.scenario_compare import compare_scenario; print(json.dumps(compare_scenario(json.load(open('fixtures/scenarios/synthetic-access.json', encoding='utf-8'))), indent=2))"
```

The synthetic fixture has one walking journey with a 200 m baseline. Its hypothetical temporary footbridge closes the two direct walking links and adds a 110 m walking connection from Side to Stop, restoring access at 190 m (-10 m). Its hypothetical vehicle-only restriction leaves the 200 m walking route unchanged. Every alternative is compared with the same baseline; unreachable destinations are returned with a null distance, while invalid or ambiguous link operations stop with an error. Added links and synthetic data are explicitly labelled; no live data or model calls are used.

Comparison mode is opt-in and keeps the confirmed walking closure fixed while comparing closure-only with two model-selected Python-owned candidate connections:

```text
python harness\ollama_scenario.py --scenario fixtures\scenarios\synthetic-comparison.json --closure-mode walking --closure-links north-origin-crossing north-crossing-destination south-origin-crossing south-crossing-destination --compare-options --question "Compare two hypothetical pedestrian mitigations for the confirmed crossing closure."
```

The synthetic comparison has two journeys and three assumed candidate connections. Python reports baseline, closure-only, and both selected options for every journey, including restored access, remaining unreachable journeys, and distance changes. The model supplies only two candidate IDs and reasons; candidate geometry, assumed lengths, and the confirmed closure remain Python-controlled.

### Named construction projects active on a date

A scenario may add a `projects` list beside `network` and `journeys`; scenarios without it, including the single-closure fixtures above, are unchanged. Each project has a unique `id`, a `label`, a required boolean `hypothetical` (validated; strings and missing values are rejected), `start_date`, `end_date` and explicit `restrictions` that reuse the existing operations (`close_links` with `"mode": "walking"`, `restrict_links` with `"mode": "vehicle"`). Dates are ISO `YYYY-MM-DD` and **both boundaries are inclusive**: a project is active when `start_date <= assessment date <= end_date`, and a one-day project has equal dates. An end date before the start date, a malformed or impossible date, a duplicate project ID, an unknown link ID or an empty restriction list stops with a message naming the project.

For one assessment date Python applies every active project together to the walking network, then reports per journey the baseline, the combined result, each project's result alone, `contributing_projects` (projects whose own closure changes the journey, or whose removal changes the combined result) and `overlap_effect` (the combination is worse than any single project). Walking-mode vehicle restrictions do not change walking routes. No model call is involved. The new `fixtures/scenarios/synthetic-projects.json` is synthetic: station-road-works runs 2026-11-10 to 2026-11-20 and mill-lane-works 2026-11-16 to 2026-11-27, overlapping 2026-11-16 to 2026-11-20.

```text
python harness/project_scenario.py --scenario fixtures/scenarios/synthetic-projects.json --date 2026-11-18
python harness/project_scenario.py --scenario fixtures/scenarios/synthetic-projects.json --date 2026-11-18 --json | python harness/render_comparison.py --output out/projects.html
python -m unittest check_project_scenarios.py -v
```

The browser report lists the assessment date, date rule, hypothetical status, active and inactive projects, and a journey table with baseline, combined and per-project results. An assessment is hypothetical when any active project is hypothetical; the status is carried in `project_assessment.hypothetical` and the combined alternative. The synthetic fixture projects are both hypothetical.

### First real-data case: Ringgata junction area to Ankerskogen

The bounded real-data scenario is saved in
`fixtures\scenarios\hamar-ringgata-ankerskogen.json`. It uses an explicit OSM
walking graph from mapped Ringgata crossing node `3223998135` in the
Ringgata–Disenvegen junction area to mapped Ankerskogen path node `331953301`
near park way `44330923`, with geometry-derived integer lengths totalling
1,384 m. The exact road-junction pedestrian node is not confirmed. The
Rollsløkken school entrance node `2284553352` is documented but disconnected
from a mapped pedestrian way, so this case does not claim school access.

```text
python -m unittest check_hamar_real_case.py -v
python -c "import json; from pathlib import Path; from harness.scenario_compare import compare_scenario; s=json.loads(Path(r'fixtures\scenarios\hamar-ringgata-ankerskogen.json').read_text(encoding='utf-8')); print(json.dumps({'comparison': compare_scenario(s)}, indent=2))" > out\hamar-ringgata-ankerskogen.json
python harness\render_comparison.py --output out\hamar-ringgata-ankerskogen.html < out\hamar-ringgata-ankerskogen.json
start out\hamar-ringgata-ankerskogen.html
```

The vehicle-only alternative leaves walking at 1,384 m. The explicitly
hypothetical pedestrian interruption closes one mapped cycleway segment and
makes this bounded route unavailable. OSM links, planning sources and the
school entrance gap remain evidence metadata; accessibility and legal access
are unknown.

To reproduce the detour check from the approved local OSM download without
copying it into the repository:

```text
python harness\import_hamar_osm.py --input fixtures\maps\ringgata.osm --template fixtures\scenarios\hamar-ringgata-ankerskogen.json --output out\hamar-ringgata-ankerskogen-map.json
python -c "import json; from pathlib import Path; from harness.scenario_compare import compare_scenario; s=json.loads(Path(r'out\hamar-ringgata-ankerskogen-map.json').read_text(encoding='utf-8')); print(json.dumps({'comparison': compare_scenario(s)}, indent=2))" > out\hamar-ringgata-ankerskogen-map-result.json
python harness\render_comparison.py --output out\hamar-ringgata-ankerskogen-map.html < out\hamar-ringgata-ankerskogen-map-result.json
start out\hamar-ringgata-ankerskogen-map.html
```

The importer uses only `highway=footway`, `path`, `pedestrian` or `cycleway`,
and ways tagged `foot=yes` or `foot=designated`; other highway types are not
walking links. The downloaded graph preserves the rest of way `1396077789`,
closes only its seven segments between the recorded endpoints, and finds a
2,332 m detour (+948 m). The wider graph does not change the 1,384 m baseline.
The generated offline page includes an SVG map built from the saved node
geometry, with nearby walking links, start and destination markers, toggles for
the baseline, detour and interrupted segments, and OpenStreetMap attribution.

The real-case Ollama comparison adds three Python-owned, hypothetical
connections: `junction-west-connector` (203 m), `central-path-connector`
(575 m), and `park-side-connector` (400 m). Their endpoints are mapped OSM
nodes; lengths are straight-line assumptions, and each requires a site check
for surface, access, safety and accessibility. The confirmed seven-segment
pedestrian interruption remains fixed in every candidate comparison. The live
saved report is opened with:

```text
start out\hamar-ringgata-ankerskogen-ollama.html
```

### Second real-data case: Furubergvegen-Måsåbekkvegen

The reusable importer takes its journeys, exact closure endpoints and
Python-owned candidate connections from
`fixtures\scenarios\hamar-furubergvegen-masabekkvegen.json`; no Hamar-specific
IDs are embedded in the importer. The public petition at
https://minsak.no/sak/3723 is reported concern evidence only. The mapped
crossing and walking links come from this reproducible public extract:

```text
python harness\import_hamar_osm.py --input fixtures\maps\furubergvegen-masabekkvegen.osm --template fixtures\scenarios\hamar-furubergvegen-masabekkvegen.json --output out\hamar-furubergvegen-masabekkvegen.json
python -c "import json; from pathlib import Path; from harness.scenario_compare import compare_scenario; s=json.loads(Path(r'out\hamar-furubergvegen-masabekkvegen.json').read_text(encoding='utf-8')); print(json.dumps({'comparison': compare_scenario(s)}, indent=2))" > out\hamar-furubergvegen-masabekkvegen-result.json
python harness\render_comparison.py --output out\hamar-furubergvegen-masabekkvegen.html < out\hamar-furubergvegen-masabekkvegen-result.json
start out\hamar-furubergvegen-masabekkvegen.html
```

The saved extract has SHA-256
`6b74c015c48f0ef4826888b3b56b30525b74a1999babc3027bf84b64c43babcf` and
contains mapped crossing way `1482019890` and connected cycleway
`1482019889`. The two illustrative journeys are 201 m and 241 m at baseline
and 362 m and 402 m after the hypothetical crossing interruption. The model
selects from three Python-owned hypothetical connections; their geometry,
length assumptions and site checks remain separate from the petition evidence.

To optionally experiment with current OSM data instead of the fixed snapshots,
download the documented bbox URL from the scenario metadata and set
`HAMAR_OSM_INPUT_DIR` to a directory containing `ringgata.osm` and/or
`furubergvegen-masabekkvegen.osm`. Do not treat those changing results as the
reviewed reproduction.
Run the bounded local selection and save it without changing the Ankerskogen
evidence:

```text
if not exist out mkdir out
python harness\ollama_scenario.py --scenario out\hamar-furubergvegen-masabekkvegen.json --closure-mode walking --closure-links osm-way-1482019890-segment-3 --compare-options --question "Compare two hypothetical pedestrian mitigations for the confirmed mapped crossing interruption." > out\hamar-furubergvegen-masabekkvegen-ollama.json
python harness\render_comparison.py --output out\hamar-furubergvegen-masabekkvegen-ollama.html < out\hamar-furubergvegen-masabekkvegen-ollama.json
start out\hamar-furubergvegen-masabekkvegen-ollama.html
```

Render a saved comparison result offline after stopping Ollama:

```text
if not exist out mkdir out
python harness\ollama_scenario.py --scenario fixtures\scenarios\synthetic-comparison.json --closure-mode walking --closure-links north-origin-crossing north-crossing-destination south-origin-crossing south-crossing-destination --compare-options --question "Compare two hypothetical pedestrian mitigations for the confirmed crossing closure." > out\synthetic-comparison-live-20261104.json
python harness\render_comparison.py --output out\synthetic-comparison.html < out\synthetic-comparison-live-20261104.json
start out\synthetic-comparison.html
python -m unittest check_comparison_renderer.py -v
```

The browser view uses only the saved Python `impact_summary` for route, distance and access claims. It labels the synthetic case and hypothetical changes, keeps model rationale in a separate unchecked-draft section, and shows a clarification without comparison cards. Malformed input does not replace an existing report.
For multi-journey mapped comparisons, the route map includes a journey selector;
switching it changes the baseline, closure, mitigation and endpoint layers and
marks the currently displayed journey.

### Reproducible Hamar submission

The two fixed OSM XML snapshots in `fixtures\maps\` are submission inputs.
They are attributed to OpenStreetMap contributors (ODbL 1.0); each scenario
records its source URL, retrieval date and SHA-256 checksum. The imported
scenario JSONs are also retained as small, inspectable derived evidence.
The fixture sanitization procedure, separate original-download and submitted
fixture hashes, removed fields, and route-distance parity are recorded in
[`fixtures\maps\README.md`](fixtures/maps/README.md) and
[`fixtures\maps\manifest.json`](fixtures/maps/manifest.json).
Current OSM downloads are optional experiments only: they may change the
network and results, and are not needed for the reviewed cases.

There are three distinct runs:

* **Offline demo:** `python harness\render_comparison.py --output out\hamar-comparison.html < fixtures\comparisons\synthetic-comparison-qwen2.5-3b.json`.
* **Evaluation:** `python -m unittest check_ringgata_demo.py check_hamar_real_case.py check_ollama_scenario.py check_comparison_renderer.py check_scenario_compare.py -v`.

The evaluation is deterministic. Its Hamar import tests use
`HAMAR_OSM_INPUT_DIR` when set, otherwise the tracked `fixtures\maps\`
directory. The Ollama unit tests mock the request and do not demonstrate a
live model result.

The local model path is opt-in. Install Ollama and pull the exact
`qwen2.5:3b` model (`ollama pull qwen2.5:3b`), then run the Ollama commands
shown in each case section. Those commands make one bounded request to
`127.0.0.1:11434`; saved JSON output can be rendered later as offline replay.
If Ollama is unavailable, the model run is a failure, not a successful
offline result.

The saved `fixtures\comparisons\synthetic-comparison-qwen2.5-3b.json` is a
small browser fixture. Its route distances and access statuses are generated
by Python from the explicitly synthetic scenario; its `proposal` rationale and
two candidate selections are the only parts copied from a recorded
`qwen2.5:3b` run. The rationale is draft text, not checked evidence.

## Interactive planning workspace

Start the local browser workspace (Python standard library only, bound to `127.0.0.1`):

```text
python hamar_workspace.py
```

Open `http://127.0.0.1:8765/` (`--port N` changes the port, `--open` launches the browser). Pick one of the mapped Hamar cases (the two presets, the wider extract, or the Hamar urban-area extract described below), a journey and an assessment date, edit the named hypothetical projects (each closes verified or hypothetical route sections; dates are inclusive), then use **Assess projects**. This is a deterministic Python calculation that works with Ollama stopped. **Compare options with AI** recalculates the assessment, then makes one bounded request to the local `qwen2.5:3b` model; Python alone computes candidate geometry and lengths, and the same active closures apply under every option. The model's prose is shown as unchecked text, and its raw reply is kept in collapsed diagnostics. Changing a date, project, section or the question marks displayed results outdated (the fingerprint is computed in Python) until recalculated.

For the presentation demo, select **Load demo**. This replaces the current case, journey, date and projects with the saved wider-map walk from Furubergvegen to Ringgata and two hypothetical projects, assessed on the sample date 2026-05-15, and makes all map layers visible. Use the **Hypothetical demo** selector to switch between no closures, Ringgata only, Furubergvegen only and both; each selection recalculates the route and map locally without Ollama. The respective modeled distances are 2,492 m, 3,440 m, 2,653 m and 3,601 m. These are hypothetical, not observed closures or measured effects. Editing the journey, date or projects exits the demo selector; select **Load demo** again to reset it.

For bus-stop access, select **Load synthetic bus scenario**, choose a destination stop, and switch between normal service and the hypothetical skipped usual stop. The map shows the fictional service, direction and stops; the results compare the walk to the usual stop with the shortest walk to a reachable stop still served by the same synthetic trip before the chosen destination. Choosing synthetic stop B as the destination demonstrates the no-alternative outcome. The fixed walking start and all synthetic stop positions are nodes on the wider saved walking network; all synthetic stops are assumed boardable. No walking closures or bus route are modeled; bus delay and boarding accessibility are unknown. This is a fictional example, not a real service, timetable, stop location, closure, delay or passenger observation. Loading it resets the walking workspace; use **Return to walking workspace** and **Load demo** to start the walking demo again.

For a published timetable example, choose a trip under **Published dated bus trip** and select **Load published bus scenario**. B21 uses inbound `INN:ServiceJourney:53561`, Hedmarktoppen to Sanderud sykehus; B23 uses outbound `INN:ServiceJourney:81731`, Stange skole to Fossumfeltet snuplass. Both are for **2026-11-12**. Their fixtures `fixtures\scenarios\hamar-b21-2026-11-12.json` and `fixtures\scenarios\hamar-b23-2026-11-12.json` record respectively 36 and 52 scheduled calls in order, quay coordinates, boarding/alighting and timing-point rules. Entur's [journey planner API](https://developer.entur.no/apis/graphql/journey-planner/query/serviceJourneys) confirmed the trips were active on that date and supplied scheduled passing times; all quay names and coordinates were cross-checked against the [national stop registry GTFS dump](https://developer.entur.no/open-data/stops). Each fixture records its exact query, URLs, retrieval time and source-response SHA-256 hashes. These are historical snapshot facts, not a live timetable or evidence of an actual closure. Entur attribution: Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS.

Both published cases now use the Hamar urban-area extract. The illustrative start is a saved walking node, not an observed passenger. With destination Øysteins gate, B21 gives 597 m to Storhamarsenteret normally and 770 m to Utfarten after the hypothetical skip, instead of Maxi at 933 m on the older wider extract. All 14 previously unassessed eligible stops can now be snapped and checked: 11 have a mapped route and three do not. Four mapped eligible stops in total, including previously mapped Svartoldervegen, have no route from the start in this graph. With destination Vognvegen/Furubergvegen, B23 gives 484 m to Svartoldervegen and 906 m to Maxi after the hypothetical skip, unchanged from the older extract. Eight of its 25 previously unassessed eligible stops can now be snapped and have mapped routes; the other 17 are outside the new rectangle, in the Stange/Ottestad direction. These comparisons concern eligible boarding stops before the specified destination, excluding the skipped usual stop.

The UI lists unassessed stops with reasons and separately lists snapped stops with no mapped route. The selected replacement is closest only among assessed reachable stops, not necessarily in reality. Platform connections are approximate: the graph-only distances end at snapped nodes, omit straight-line offsets (B21: 0.7 m and 2.7 m; B23: 8.1 m and 6.0 m), and do not establish physical access, crossing safety or accessibility. Only mapped alightable destinations are offered; the destination itself need not have a walking route from the start. Bus delay is unknown and no bus route or walking closure is modeled. The separate synthetic S1 demo remains available.

### Preparing a walking map

The operational **Hamar urban-area** boundary is the rectangle longitude 11.020–11.140, latitude 60.780–60.840 (about 6.5 × 6.6 km). It includes the central Hamar area and the two walking-demo areas, with some neighbouring areas. This is a practical study rectangle, **not an official municipal or urban-settlement boundary** and not proof that every part of Hamar or every walkable route is covered. Rural parts, trip endpoints beyond the rectangle, missing OSM ways, disconnected components, and ways excluded by the existing walking-tag policy remain gaps. The saved 2026-11-12 snapshot has 16,319 routable nodes and 16,619 links; ways crossing the edge can include nodes just outside it.

To prepare a fresh extract, choose a study boundary and enough tiles to stay within the OSM API's limits (more tiles may be needed for dense areas). For example:

```text
python harness\prepare_walking_map.py --bounds 11.02 60.78 11.14 60.84 --columns 6 --rows 3 --output fixtures\maps\hamar-urban-new.osm --metadata hamar-urban-entry.json
```

The arguments are west, south, east, north in degrees; rows and columns form a complete rectangular grid. The command downloads the OSM API tiles, checks their bounds, merges and sanitizes them with the existing helpers, validates retained node references, and writes a manifest-entry JSON with URLs, per-tile retrieval times and hashes, merged hash and sanitized hash. Raw downloads are temporary and are not fixtures. Requests are sequential, not an atomic historical snapshot; rerunning against current OSM can change the map and routes. The API can reject a dense tile even below its area limit: increase rows or columns and retry responsibly. Copy the entry into `fixtures\maps\manifest.json`, configure a walking scenario and `CASES` entry in `harness\workspace_service.py`, and verify its journeys, closures and routes against the new map before use. The workspace verifies the fixture hash on load. The supplied urban case reuses the wider Hamar scenario template, so its Hamar-specific nodes and closures are not a generic city template.

To add another published service, save a fixture in the same format as the B21/B23 files: verify a dated trip's full ordered calls, boarding/alighting and timing-point rules against an official timetable, verify quay IDs and coordinates against official stop data, record sources and hashes, and choose an illustrative origin node, boardable usual stop and later alightable destination. Set `case_id` to a configured walking-map case and add an ID-to-filename entry in `PUBLISHED_BUS_CASES` in `harness\workspace_service.py`; the selector and assessment use that list. Check snap offsets, graph connectivity, excluded stops and no-alternative cases; snapping alone does not establish a physical connection.

For another city, use the preparation command with that city's chosen bounds, tile grid and output paths; then prepare a matching walking scenario and add its `CASES` configuration, including map, journeys and closure sections. Create a sourced bus fixture linked to that case, review the 75 m snap limit and map coverage, and replace city-specific labels, coordinate examples, planning sources and the hard-coded Hamar walking demo in the workspace. The legacy `/api/bus/published` and `published` assessment alias default to the first configured published case; update or retire them as appropriate. These are migration steps, not existing multi-city support.

Custom walking journeys: choose **Choose start on map** / **Choose destination on map** and click the map (or enter coordinates under the journey selector). The server snaps each point to the nearest mapped walking node within 75 m and routes with the same shortest-route and project-assessment code as the presets; closure sections for the custom route appear in the project form. Three outcomes are kept distinct: a point outside the loaded extract (or more than 75 m from the nearest mapped walking node) is reported as **outside map coverage** and not assessed; a journey with no baseline route is **no mapped route**; a journey connected in the baseline without closures but cut by the active closures is **unreachable under closures**. Coverage is the OSM bounds of the selected saved fixture only (Furubergvegen/Måsåbekkvegen: lat 60.800–60.810, lon 11.040–11.055; Ringgata: lat 60.796–60.805, lon 11.060–11.090; wider extract: lat 60.796–60.810, lon 11.040–11.090; urban extract: lat 60.780–60.840, lon 11.020–11.140). The two preset cases are separate extracts; the wider and urban extracts connect both areas. Ways that cross the bounds keep their outside nodes, so a detour can run slightly beyond the dashed outline, but the map is still cut at its edge and real alternatives beyond it are not seen. The AI comparison still covers only the preset journeys.

Limits: walking mode only (other modes are planned); the cases come from saved sanitized OpenStreetMap fixtures; only the mapped section or crossing named in the planning notice reflects the real notice, and the closure applied to it in the tool is still hypothetical; all other sections are hypothetical too; connector lengths are planning allowances, not verified feasibility. The server accepts only fixed case IDs, bounded coordinates and JSON bodies up to 32 KB, rejects foreign `Host`/`Origin` headers, and has no file-path or shell inputs. Checks: `python -m unittest check_workspace.py` (synthetic, fake Ollama).

## Local Ollama planner

Ask the installed `qwen2.5:3b` model for one draft alternative against a saved scenario:

```text
python harness\ollama_scenario.py --scenario fixtures\scenarios\synthetic-access.json --closure-mode walking --question "Close the direct crossing for pedestrians during a hypothetical works period."
```

The command makes one bounded local request, then prints the model proposal separately from Python's checked route comparison. `--closure-mode walking` or `--closure-mode vehicle` is planner-confirmed scope. A closure question without that flag returns a clarification before any comparison. Model references, operation modes, hypothetical added links and assumed lengths are validated before the existing scenario engine runs. Ollama failures and malformed responses stop clearly. Use another scenario JSON with the same command; the baseline network and journeys remain Python-controlled.

## Project history: Task 007 bounded bus collection

The collector is implemented in [harness/collect_bus_sample.py](harness/collect_bus_sample.py). It defaults to a no-mutation, no-network dry-run:

```text
python harness/collect_bus_sample.py --mode dry-run
```

The dry-run prints the exact Entur endpoint, public client identifier, `Accept` header, one-request/5 MiB/20-second bounds and destination. It does not create the output directory or claim a capture. A synthetic SIRI XML response can be replayed offline:

```text
python harness/collect_bus_sample.py --mode replay --response-file out/task007-synthetic-response.xml --output-root out/bus-collection
```

Replay writes a unique directory containing `snapshot.json` and `manifest.json`, marks the result synthetic/offline, preserves provider timestamps and records replay execution time separately. Open those JSON files directly to inspect the filtered snapshot and provenance. The source body is never saved by the collector; synthetic input files are test data only.

Live mode is explicit and is not required for this task:

```text
python harness/collect_bus_sample.py --mode live --output-root out/bus-collection
```

It makes one bounded request only, uses the fixed public endpoint and headers, rejects redirects/non-XML/error responses, and applies local lock and cooldown coordination within that output root. It is not background collection, scheduling, complete Hamar coverage or integration with the existing historical report. Live preflight and remote CI remain pending; no live request is needed yet.

Run the independent offline checks:

```text
python scripts/verify_bus_collection.py
```

The verifier uses synthetic XML and mocked transport only, creates fresh ignored `out/bus-collection-verification/checks-*/` evidence, and must be run alongside the existing route and traffic verifiers. The collection snapshot is a new schema and must not be passed to the Task 006 historical report without a later integration task.

## Project history: Task 006 saved route coverage at three stops

Run from the repository root with standard-library Python:

```text
python harness/route_coverage_report.py --input fixtures/hamar-route-coverage-2026-10-21.json --output-dir out/route-coverage
python scripts/verify_route_coverage.py
```

The producer writes self-contained `out/route-coverage/route-coverage.html` and `route-coverage.json`. This saved 21 October snapshot inventories six verified quays at Storhamarsenteret, Hamar skysstasjon and CC Hamar from one bounded first page of 100 INN journeys. Observed routes are B21 (6 journeys, 18 calls, 10 actual/8 prediction-only), B22 (3 journeys, 6 calls, 3 actual/3 prediction-only) and 660 (1 journey, 2 calls, 0 actual/2 prediction-only). Totals: 10 distinct observed journeys, 26 calls, 13 actual and 13 prediction-only; zero unknown/cancelled. Route 660's lack of actual comparisons describes data availability, not proof of poor service.

B22 actual observations are now represented by this saved-data component. Repeated-day capture and the main AI catalogue integration remain pending; the existing AI briefing does not automatically cover B22. This is no complete city/day survey; absence from the subset does not establish absence of a service. Predictions remain separate, missing data is unknown, provider actuals are not independently verified physical events and counts are not passenger counts. No recurring patterns, causes, performance ranking or municipal benefit are demonstrated.

The new verifier uses fresh ignored `out/route-coverage-verification/checks-*/` directories and records commands, stdout/stderr, exits, assertions and `summary.json`. Mutations are synthetic software checks, not live or repeated-day experiments. The existing nine traffic cases remain unchanged. The Windows/Ubuntu workflow now also runs the route verifier; remote CI for this addition remains **pending**. See `tasks/006-route-coverage-sample.md` for local evidence.

## Project history: Task 005 repeatable offline verification

From the repository root, with standard-library Python (CI uses Python 3.12):

```text
python scripts/verify_traffic.py
```

Exit 0 and `PASS: 9/9 offline cases; zero model requests` mean all expected results were checked. An expected controller rejection passes its test; any unexpected result, timeout or failed assertion makes the verifier exit nonzero and identify the failed case. Each execution creates a fresh ignored directory under `out/traffic-verification/`, with synthetic decisions, copied/mutated inputs, per-case commands, stdout/stderr, actual exit codes, assertions and `summary.json`. Controller run paths come from each invocation's output and are checked to stay inside `out/traffic-brief/`.

Checks use saved real fixtures and synthetic decisions, only prepare/replay modes, zero model invocations and no live data. They cover reviewed fact anchors/provenance, accepted JSON/HTML content, unknown/duplicate IDs, malformed/missing input and unavailable actual statistics. Missing actuals remain unknown, while predictions remain separate. Content checks are not visual or accessibility inspection, usefulness evaluation or proof of recurring performance.

The `Traffic offline verification` GitHub workflow runs the same command on PRs targeting main, pushes to main and manual dispatch, using Ubuntu/Windows with Python 3.12. After a remote run, open the PR's **Checks** tab (or repository **Actions**) and inspect both matrix jobs and their logs. Initial GitHub run `39803550320` passed on Windows and Ubuntu. In a deliberate test exercise, commit `8724b9d` changed the correct road-total expectation 19576 to 19577; Ubuntu job `119914885500` in run `39804761955` rejected it (prepare, valid-replay and no-actuals-prepare failed; 6/9 passed, exit 1). This was an intentionally incorrect test expectation, not an application defect. Restoring 19576 locally passed all nine cases, exit 0; remote checks after this repair remain **pending**. Official action/runtime setup normally downloads components; the Python verifier is offline, without an isolated runner network sandbox. Task evidence and remaining limits are recorded in `tasks/005-offline-traffic-checks.md`.

## Project history: Task 004 checked briefing workflow

Run from the repository root (mode is always explicit):

```text
python harness/traffic_brief.py --mode prepare
```

Synthetic replay (offline, not real AI execution): create an ignored JSON decision file under `out/` so the offline replay is reproducible without relying on the temporary `out/task004-checks-domzmx58/valid.json` path from a prior run. PowerShell example:

```powershell
New-Item -ItemType Directory -Force -Path out | Out-Null
$decision = @{
    highlight_ids = @('bus.actual_max_seconds', 'road.vang_kirke.peak')
    followup_ids = @('collect_same_day_samples')
}
$decision | ConvertTo-Json -Compress | Set-Content -Path 'out/task004-synthetic-decision.json' -Encoding utf8
```

Exact synthetic contents written to `out/task004-synthetic-decision.json`:

```json
{"highlight_ids":["bus.actual_max_seconds","road.vang_kirke.peak"],"followup_ids":["collect_same_day_samples"]}
```

Replay using that reproducible path:

```text
python harness/traffic_brief.py --mode replay --decision-file out/task004-synthetic-decision.json
```

This replay is labelled OFFLINE REPLAY and never establishes AI execution. Prepare stops after computing facts and reading runtime context. Each command prints its unique directory under `out/traffic-brief/`, containing `trace.json`, `facts.json` and `prompt.txt` after valid input preparation. Checked replay also writes `checked-decision.json`, `briefing.json` and self-contained `briefing.html`. Failed runs record a reason and never reuse an older briefing as current.

Real AI execution succeeded with the existing installed/logged-in Codex CLI. Working command from the repository root:

```text
python harness/traffic_brief.py --mode codex --codex-path "C:\Users\moham\.codex\packages\standalone\current\bin\codex.exe"
```

The saved successful runs used the configured permission override. An optional `--codex-path` selects an existing executable; otherwise PATH and the known standalone Windows install are checked. No model override is used and login files are never inspected. The child uses a one-time narrowed named permission profile (read-only, .env/.env.local denied, command networking disabled), not modified permission files or bypass flags. The earlier non-model diagnostic failed with Access is denied, but the later real runs completed with this override. Successful runs do not independently prove permission enforcement or timeout/process-tree controls.

On 22 October 2026, saved runs `out/traffic-brief/20261022T143808Z-e3red74e` and `out/traffic-brief/20261022T144225Z-x1srsxg5` each recorded process exit 0, one Codex invocation, a completed turn, checked decisions and rendered HTML/JSON briefings. Both used saved real data: road observations from 20 October and bus observations from 21 October, not new live collection or synthetic decisions.

Both selected `road.vang_kirke.total` (19,576 vehicle passages), `bus.actual_count` (10 stop-call comparisons), `bus.actual_min_seconds` (-88 signed seconds) and `bus.actual_max_seconds` (289 signed seconds), with `collect_same_day_samples` and `check_early_departure_records` as follow-ups.

Reported usage was 17,513 input / 54 output tokens for `20261022T143808Z-e3red74e` and 17,514 input / 54 output tokens for `20261022T144225Z-x1srsxg5`. Both reported zero cached-input, cache-write-input and reasoning-output tokens.

The controller permits one model invocation, no controller retries, a 12,000-character prompt, 120-second child timeout, 4,096-byte decision and bounded 1 MiB stdout/1 MiB stderr capture. Tool events, failed turns and invalid selections are rejected. Reported token usage is retained when available. These are invocation/time/size controls, **not a proven hard token or monetary budget**. The model selects IDs only; program-owned verified facts/questions are rendered. Compare selection usefulness with a deterministic baseline before claiming AI superiority. Recurring acquisition, repeated-day evidence, that evaluation and a hard budget remain outstanding.

Task 004 offline checks verified all ten fact anchors, source dates/hashes, context read, a valid replay, unknown-ID rejection and malformed-input rejection; all recorded zero Codex invocations. See `tasks/004-checked-traffic-brief.md` for actual commands, runs, outputs and blocked diagnostics. HTML visual inspection remains pending.

Run separately from the repository root:

```text
python harness/traffic_report.py --input fixtures/hamar-traffic-2026-10-20.json --output-dir out
python harness/bus_timing_report.py --input fixtures/hamar-b21-timing-2026-10-21.json --output-dir out
```

Open `out/traffic-report.html` and `out/bus-timing-report.html`; matching JSON files retain provenance, detailed values and summaries. Actual verification is recorded in `tasks/002-traffic-baseline.md` and `tasks/003-bus-timing-sample.md`.

Road data: [Statens vegvesen traffic-data API](https://trafikkdata-api.atlas.vegvesen.no), three separate counters on 20 October 2026. Vehicle passages do not measure unique travellers, congestion or bus delay.

Bus attribution: Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS. [NLOD licence](https://data.norge.no/nlod/no/2.0), [Entur realtime documentation](https://developer.entur.no/open-data/realtime), [terms](https://developer.entur.no/terms-of-service), [getting started](https://developer.entur.no/docs/getting-started).

The filtered B21 snapshot contains six journeys and 18 calls at three stops from one bounded 100-journey INN response on 21 October 2026, not complete regional coverage. Other calls and vehicle/staff identifiers were excluded. The retained response hash describes the original whole response, not the fixture bytes. Source-reported actuals are provider observations, not independently verified physical events or evidence of a legal service breach. Predictions are separate; missing comparisons are unknown and cancelled calls are excluded. Negative differences are preserved.

The road and bus samples are on different dates and are not simultaneous observations. These samples do not establish recurring delay rates, passenger harm, causes or intervention success. Recurring acquisition, repeated-day evidence, usefulness evaluation and actual municipal benefit remain pending.

## Project history: funding preparation: first component

The checker classifies a declared timeline-preparation answer and reads the source URL from the saved JSON rule. `True` means `declared_present`, not verified document contents.

The tests use synthetic answers and a saved real rule. Python's standard library is sufficient. Run from the repository root:

```text
python -m unittest discover -s eval -p check_funding_timeline.py -v
```

Expected result: four tests and `OK`.

Rule interpretation, document/date validation, AI stages and the website remain unimplemented.

## Project history: Task 001 offline source probe

The probe reads the saved public-rule excerpt in `fixtures/funding-timeline-rule.json` and generates `out/probe.json`, copying the source URL, checked date, rule ID and quote unchanged.

Run these commands separately from the repository root:

```text
python harness/probe.py
```

```text
python eval/check_probe.py
```

```text
python -m unittest discover -s eval -p check_probe_inputs.py -v
```

Expected: the producer is normally silent, the checker prints `PASS`, and three tests report `OK`. The synthetic cases cover missing input, invalid JSON and missing `source_quote`; each checks that neither the output file nor its parent directory is created.
