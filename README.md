# Hamar traffic and bus reliability ? provisional project

Intended users are transport staff reviewing recurring road patterns and bus timing evidence around Hamar. These standard-library components use genuine saved samples offline; recurring collection and runtime AI remain pending.

Run separately from the repository root:

```text
python harness/traffic_report.py --input fixtures/hamar-traffic-2026-10-20.json --output-dir out
python harness/bus_timing_report.py --input fixtures/hamar-b21-timing-2026-10-21.json --output-dir out
```

Open `out/traffic-report.html` and `out/bus-timing-report.html`; matching JSON files retain provenance, detailed values and summaries. Actual verification is recorded in `tasks/002-traffic-baseline.md` and `tasks/003-bus-timing-sample.md`.

Road data: [Statens vegvesen traffic-data API](https://trafikkdata-api.atlas.vegvesen.no), three separate counters on 20 October 2026. Vehicle passages do not measure unique travellers, congestion or bus delay.

Bus attribution: Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS. [NLOD licence](https://data.norge.no/nlod/no/2.0), [Entur realtime documentation](https://developer.entur.no/open-data/realtime), [terms](https://developer.entur.no/terms-of-service), [getting started](https://developer.entur.no/docs/getting-started).

The filtered B21 snapshot contains six journeys and 18 calls at three stops from one bounded 100-journey INN response on 21 October 2026, not complete regional coverage. Other calls and vehicle/staff identifiers were excluded. The retained response hash describes the original whole response, not the fixture bytes. Source-reported actuals are provider observations, not independently verified physical events or evidence of a legal service breach. Predictions are separate; missing comparisons are unknown and cancelled calls are excluded. Negative differences are preserved.

The road and bus samples are on different dates and are not simultaneous observations. These samples do not establish recurring delay rates, passenger harm, causes or intervention success. Recurring acquisition, repeated-day evidence, checked AI briefings and actual municipal benefit remain pending.

## Earlier weather practice exercise

Run `python server.py` and open http://127.0.0.1:8000.

Tomorrow is calculated in Europe/Oslo. Forecasts come from MET Norway Locationforecast for Hamar (60.7945, 11.0679), through a Python proxy. No dependencies or API key are needed.

Forecasts are cached in memory until MET’s `Expires` time. After expiry, the server uses `Last-Modified` for a conditional request when available. HTTP 304 means the cached forecast can be retained. Missing or invalid expiry causes revalidation on the next request. The cache resets when the server restarts.

Before running any API request, set `MET_USER_AGENT` to an application identifier with your genuine contact email or project URL, as required by MET Norway. The server refuses to contact the API when this setting is missing. Use the same identifier for connectivity checks. A successful API request verifies connectivity only; it does not verify date selection or webpage rendering.

Forecast data: MET Norway, CC BY 4.0. Low/high temperatures use hourly samples; precipitation totals appear only when hourly precipitation is available throughout tomorrow.

## Funding preparation: first component

The checker classifies a declared timeline-preparation answer and reads the source URL from the saved JSON rule. `True` means `declared_present`, not verified document contents.

The tests use synthetic answers and a saved real rule. Python's standard library is sufficient. Run from the repository root:

```text
python -m unittest discover -s eval -p check_funding_timeline.py -v
```

Expected result: four tests and `OK`.

Rule interpretation, document/date validation, AI stages and the website remain unimplemented.

## Task 001: offline source probe

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
