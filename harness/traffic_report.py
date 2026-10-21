"""Generate the fixed-date traffic baseline from a saved response, offline."""

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


POINTS = {
    "vang_kirke": ("26093V704634", "Vang kirke"),
    "disen_ost": ("10220V704634", "Disen øst"),
    "vangsvegen_91": ("37879V2488949", "Vangsvegen 91"),
}
START = datetime(2026, 10, 20, tzinfo=timezone(timedelta(hours=2)))
LIMITATION = "Vehicle counts alone do not measure congestion, bus delay or unique travellers."


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    require(isinstance(value, str), "Timestamp must be a string")
    result = datetime.fromisoformat(value)
    require(result.utcoffset() is not None, "Timestamp must include a UTC offset")
    return result


def analyse(saved):
    require(type(saved["http_status"]) is int and saved["http_status"] == 200,
            "Saved HTTP response must have status 200")
    source = urlsplit(saved["source"])
    require(source.scheme == "https" and source.hostname == "trafikkdata-api.atlas.vegvesen.no"
            and not source.username and not source.password, "Invalid traffic source URL")
    timestamp(saved["retrieved_at_utc"])
    require(not saved["response"].get("errors"), "Saved response contains GraphQL errors")
    require(saved["points"] == {key: value[0] for key, value in POINTS.items()},
            "Expected exactly the three observed counter IDs")
    data = saved["response"]["data"]
    require(set(data) == set(POINTS), "Data entries must match the three counters")
    query = saved["request_query"]
    require(isinstance(query, str), "Missing request query")
    summaries = []
    for key, (counter_id, name) in POINTS.items():
        pattern = rf'\b{re.escape(key)}\s*:\s*trafficData\s*\(\s*trafficRegistrationPointId\s*:\s*"{re.escape(counter_id)}"\s*\)'
        require(len(re.findall(pattern, query)) == 1,
                f"{key}: request query must match counter ID")
        edges = data[key]["volume"]["byHour"]["edges"]
        require(isinstance(edges, list) and len(edges) == 24,
                f"{key}: expected exactly 24 hourly records")
        hourly = []
        seen = set()
        for edge in edges:
            node = edge["node"]
            begin, end = timestamp(node["from"]), timestamp(node["to"])
            require(begin.utcoffset() == end.utcoffset() == timedelta(hours=2),
                    f"{key}: hourly timestamps must use UTC+02:00")
            require(begin in {START + timedelta(hours=i) for i in range(24)}
                    and end == begin + timedelta(hours=1) and begin not in seen,
                    f"{key}: invalid, duplicate or non-contiguous hourly interval")
            seen.add(begin)
            count = node["total"]["volumeNumbers"]["volume"]
            coverage = node["total"]["coverage"]["percentage"]
            require(type(count) is int and count >= 0,
                    f"{key}: volume must be a non-negative integer (not null or boolean)")
            require(type(coverage) in (int, float) and math.isfinite(coverage)
                    and 0 <= coverage <= 100, f"{key}: coverage must be a number from 0 to 100")
            hourly.append({"from": begin.isoformat(), "to": end.isoformat(),
                           "volume": count, "coverage_percentage": coverage})
        hourly.sort(key=lambda row: row["from"])
        peak = max(row["volume"] for row in hourly)
        summaries.append({"source_key": key, "counter_id": counter_id, "name": name,
                          "records": len(hourly),
                          "daily_vehicle_passages": sum(row["volume"] for row in hourly),
                          "peak_vehicle_passages": peak,
                          "peak_intervals": [{"from": row["from"], "to": row["to"]}
                                             for row in hourly if row["volume"] == peak],
                          "hours_below_100_percent_coverage": sum(
                              row["coverage_percentage"] < 100 for row in hourly),
                          "hourly": hourly})
    return {"date": "2026-10-20", "timezone": "Europe/Oslo (UTC+02:00)",
            "provenance": {key: saved[key] for key in
                           ("source", "retrieved_at_utc", "http_status", "request_query", "points")},
            "limitation": LIMITATION, "counters": summaries}


def render(report):
    sections = []
    for counter in report["counters"]:
        rows, bars = [], []
        for hour in counter["hourly"]:
            interval = hour["from"][11:16] + "–" + hour["to"][11:16]
            label = f'{interval}: {hour["volume"]:,} passages; coverage {hour["coverage_percentage"]:g}%'
            bars.append(f'<div class="bar" style="height:{hour["volume"] / counter["peak_vehicle_passages"] * 100 if counter["peak_vehicle_passages"] else 0:.2f}%" title="{escape(label, quote=True)}"></div>')
            rows.append(f'<tr><td>{escape(interval)}</td><td>{hour["volume"]:,}</td><td>{hour["coverage_percentage"]:g}%</td></tr>')
        peaks = ", ".join(p["from"][11:16] + "–" + p["to"][11:16] for p in counter["peak_intervals"])
        sections.append(f'''<section><h2>{escape(counter["name"])}</h2>
<p>Counter {escape(counter["counter_id"])} · {counter["records"]} hourly records</p>
<p><strong>{counter["daily_vehicle_passages"]:,} daily vehicle passages</strong><br>
Peak: {counter["peak_vehicle_passages"]:,} passages, {escape(peaks)}.<br>
Hours below 100% reported coverage: {counter["hours_below_100_percent_coverage"]}.</p>
<div class="chart" role="img" aria-label="Hourly vehicle passages; exact values in table below">{''.join(bars)}</div>
<p class="axis">00:00 — Local hour (each bar is one hour) — 24:00</p>
<details><summary>Hourly passages and reported coverage</summary><table><thead><tr><th>Local interval</th><th>Vehicle passages</th><th>Coverage</th></tr></thead><tbody>{''.join(rows)}</tbody></table></details></section>''')
    provenance = report["provenance"]
    return f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Hamar traffic baseline</title>
<style>body{{font:17px system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#172b3a;background:#f5f8fa}}section{{background:white;padding:1.5rem;margin:1.5rem 0;border:1px solid #cbd5dc;border-radius:8px}}.chart{{height:180px;display:flex;align-items:end;gap:3px;border-bottom:1px solid #456}}.bar{{flex:1;background:#17678b;min-width:1px}}.axis{{font-size:.85rem}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:.35rem;border-bottom:1px solid #ddd}}.limitation{{padding:1rem;background:#fff1ca}}</style>
<h1>Hamar road-counter baseline</h1><p>Source date: {escape(report["date"])} · {escape(report["timezone"])}</p>
<p class="limitation">{escape(LIMITATION)} These are vehicle passages at separate counters, not one-direction flow counts. Counters are not summed across locations.</p>
<p>Offline report from saved observations. Source: {escape(provenance["source"])}<br>Retrieved: {escape(provenance["retrieved_at_utc"])}</p>
{''.join(sections)}</html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        root = Path(__file__).resolve().parents[1] / "out"
        destination = args.output_dir.resolve()
        require(destination == root or root in destination.parents,
                "Output directory must be under repository out/")
        report = analyse(json.loads(args.input.read_text(encoding="utf-8")))
        json_text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        html_text = render(report)
        destination.mkdir(parents=True, exist_ok=True)
        json_path, html_path = destination / "traffic-report.json", destination / "traffic-report.html"
        json_path.write_text(json_text, encoding="utf-8")
        html_path.write_text(html_text, encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        print(f"Traffic report failed: {exc}. No successful new report; any existing outputs may be stale.", file=sys.stderr)
        return 1
    print(f"Generated {json_path} and {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
