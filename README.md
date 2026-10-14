# Hamar weather

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
