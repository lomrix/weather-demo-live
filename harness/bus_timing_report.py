"""Offline B21 departure comparisons from a filtered saved Entur snapshot."""

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


STOPS = {"CC Hamar", "Hamar skysstasjon", "Storhamarsenteret"}
TIMES = tuple(prefix + suffix for prefix in ("Aimed", "Actual", "Expected")
              for suffix in ("ArrivalTime", "DepartureTime"))
CATEGORIES = ("actual", "prediction_only", "unknown", "cancelled")
LOCAL = timezone(timedelta(hours=2))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    require(isinstance(value, str) and bool(value.strip()), "Expected non-empty text")
    return value


def scalar(value):
    if isinstance(value, dict):
        return scalar(value["value"])
    if isinstance(value, list):
        require(len(value) == 1, "Expected one value in selected text list")
        return scalar(value[0])
    return text(value)


def stamp(value):
    text(value)
    require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value)),
            f"Malformed timestamp: {value!r}")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.utcoffset() is not None, "Timestamp requires UTC offset")
    return result


def flag(record):
    value = record.get("Cancellation", False)
    require(type(value) is bool, "Cancellation must be boolean when supplied")
    return value


def analyse(saved):
    require(isinstance(saved, dict), "Input must be an object")
    require(type(saved["http_status"]) is int and saved["http_status"] == 200,
            "Saved HTTP status must be 200")
    source = urlsplit(text(saved["source_url"]))
    require(source.scheme == "https" and source.netloc == "api.entur.io"
            and source.path == "/realtime/v1/rest/et", "Invalid Entur source URL")
    stamp(saved["retrieved_at_utc"])
    require(parsedate_to_datetime(text(saved["server_date"])).utcoffset() is not None,
            "Server date requires offset")
    text(saved["client_identifier"])
    require(bool(re.fullmatch(r"[0-9a-f]{64}", text(saved["response_sha256"]))),
            "Invalid original-response SHA256")
    text(saved["attribution"])
    require(saved["licence_url"] == "https://data.norge.no/nlod/no/2.0", "Expected NLOD licence")
    require(saved["modified"] is True, "Filtered selection must be disclosed")
    selection = saved["selection"]
    require(selection["line"] == "B21" and isinstance(selection["stop_names"], list)
            and len(selection["stop_names"]) == 3 and set(selection["stop_names"]) == STOPS,
            "Expected B21 and the three selected Hamar stops")
    text(selection["description"])
    journeys = saved["journeys"]
    require(isinstance(journeys, list) and bool(journeys), "Expected journey list")
    calls, journey_ids, identities = [], set(), set()
    for journey in journeys:
        require(scalar(journey["PublishedLineName"]) == "B21"
                and scalar(journey["LineRef"]) == "INN:Line:21", "Journey must identify B21")
        stamp(journey["RecordedAtTime"])
        framed = journey["FramedVehicleJourneyRef"]
        frame = scalar(framed["DataFrameRef"])
        require(frame == "2026-10-21", "Unexpected service date")
        journey_id = scalar(framed["DatedVehicleJourneyRef"])
        direction = scalar(journey["DirectionRef"])
        identity = (frame, journey_id)
        require(identity not in journey_ids, "Duplicate journey")
        journey_ids.add(identity)
        journey_cancelled = flag(journey)
        count = 0
        for group, singular in (("RecordedCalls", "RecordedCall"), ("EstimatedCalls", "EstimatedCall")):
            if group not in journey:
                continue
            records = journey[group][singular]
            require(isinstance(records, list), f"{group} must contain a list")
            for call in records:
                stop, stop_id = scalar(call["StopPointName"]), scalar(call["StopPointRef"])
                require(stop in STOPS, "Call outside selected stops")
                order = call["Order"]
                require(type(order) is int and order >= 0, "Call order must be a non-negative integer")
                key = (frame, journey_id, order)
                require(key not in identities, "Duplicate call order within journey")
                identities.add(key)
                count += 1
                # Parse every provided time, even if cancellation or another field prevents comparison.
                supplied = {field: call[field] for field in TIMES if field in call}
                parsed = {field: stamp(value) for field, value in supplied.items() if value is not None}
                call_cancelled = flag(call)
                cancelled = journey_cancelled or call_cancelled
                aimed = parsed.get("AimedDepartureTime")
                actual = parsed.get("ActualDepartureTime")
                expected = parsed.get("ExpectedDepartureTime")
                category, difference = "unknown", None
                if cancelled:
                    category = "cancelled"
                elif aimed is not None and actual is not None:
                    category, difference = "actual", (actual - aimed).total_seconds()
                elif actual is None and aimed is not None and expected is not None:
                    category, difference = "prediction_only", (expected - aimed).total_seconds()
                calls.append({"journey_id": journey_id, "data_frame_ref": frame,
                              "direction": direction, "line_ref": scalar(journey["LineRef"]),
                              "line_name": scalar(journey["PublishedLineName"]),
                              "recorded_at": journey["RecordedAtTime"],
                              "source_call_group": group, "stop_id": stop_id, "stop_name": stop,
                              "order": order, "journey_cancelled": journey_cancelled,
                              "call_cancelled": call_cancelled, "times": supplied,
                              "category": category, "departure_difference_seconds": difference,
                              "missing_departure_fields": [field for field in
                                  ("AimedDepartureTime", "ActualDepartureTime", "ExpectedDepartureTime")
                                  if field not in parsed]})
        require(count > 0, "Journey contains no selected calls")
    require({row["stop_name"] for row in calls} == STOPS, "Missing selected stop")
    counts = {category: sum(row["category"] == category for row in calls) for category in CATEGORIES}
    actuals = [row["departure_difference_seconds"] for row in calls if row["category"] == "actual"]
    return {"provenance": {key: saved[key] for key in
                           ("source_url", "client_identifier", "retrieved_at_utc", "http_status",
                            "server_date", "response_sha256", "attribution", "licence_url", "modified")},
            "selection": selection, "calls": calls,
            "summary": {"journeys": len(journey_ids), "calls": len(calls), "categories": counts,
                        "actual_difference_seconds": {"sum": sum(actuals) if actuals else None,
                                                      "min": min(actuals) if actuals else None,
                                                      "max": max(actuals) if actuals else None},
                        "by_stop": {stop: {"calls": sum(row["stop_name"] == stop for row in calls),
                                          **{category: sum(row["stop_name"] == stop and row["category"] == category
                                                           for row in calls) for category in CATEGORIES}}
                                    for stop in sorted(STOPS)}}}


def render(report):
    def esc(value):
        return escape(str(value), quote=True)

    def local(value):
        return stamp(value).astimezone(LOCAL).isoformat(sep=" ") if value else "Unavailable"

    sections = []
    for category, heading in (("actual", "Source-reported actual departures"),
                              ("prediction_only", "Prediction-only departures"),
                              ("unknown", "Unknown comparisons"), ("cancelled", "Cancelled calls")):
        rows = []
        for call in report["calls"]:
            if call["category"] != category:
                continue
            times = call["times"]
            difference = call["departure_difference_seconds"]
            values = [call["stop_name"], call["journey_id"], call["direction"], call["order"],
                      call["stop_id"], call["source_call_group"],
                      *(local(times.get(field)) for field in
                        ("AimedDepartureTime", "ActualDepartureTime", "ExpectedDepartureTime")),
                      f"{difference:+g}" if difference is not None else "Unavailable"]
            rows.append("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in values) + "</tr>")
        sections.append(f'<h2>{heading} ({report["summary"]["categories"][category]})</h2>'
                        '<div class="scroll"><table><thead><tr>' + ''.join(f'<th>{label}</th>' for label in
                        ("Stop", "Journey", "Direction", "Order", "Stop ID", "Source group", "Scheduled departure",
                         "Reported actual departure", "Predicted departure", "Signed seconds")) +
                        '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
    p = report["provenance"]
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>B21 Hamar timing snapshot</title><style>body{{font:16px system-ui,sans-serif;margin:2rem;color:#172b3a}}table{{border-collapse:collapse}}th,td{{padding:.6rem;text-align:left;border:1px solid #ccd}}.scroll{{overflow-x:auto}}.notice{{background:#fff0c4;padding:1rem}}</style>
<h1>B21 Hamar departure timing snapshot</h1>
<p>Retrieved: {esc(p["retrieved_at_utc"])}; local: {esc(local(p["retrieved_at_utc"]))}. Server date: {esc(p["server_date"])}. Display times: Europe/Oslo, UTC+02:00 on 21 October 2026.</p>
<p class="notice">Actual times are source-reported provider observations, not independently verified physical events or evidence of a legal service breach. Predictions are kept separate. Signed seconds mean departure minus scheduled time; negative values mean earlier departures. Unknown comparisons are unavailable, never zero-filled. Cancelled calls are excluded from comparisons.</p>
<p>Filtered/modified data: {esc(report["selection"]["description"])} First page of 100 INN journeys; no complete regional coverage. This sample does not establish recurring delay rates, passenger harm, delay causes or intervention success. The road sample is dated 20 October; these bus calls are dated 21 October and are not simultaneous observations.</p>
<p>{esc(p["attribution"])} <a href="{esc(p["licence_url"])}">NLOD licence</a> · <a href="{esc(p["source_url"])}">Saved request source</a> · <a href="https://developer.entur.no/open-data/realtime">Entur realtime documentation</a></p>
<p>{report["summary"]["journeys"]} journeys; {report["summary"]["calls"]} calls. Unknown: {report["summary"]["categories"]["unknown"]}; cancelled: {report["summary"]["categories"]["cancelled"]}.</p>
<p>Actual-only signed seconds (sum/min/max): {esc(report["summary"]["actual_difference_seconds"])}. These are sample statistics, not daily or city-wide delay measures.</p>
{''.join(sections)}<p>Original whole-response SHA256: {esc(p["response_sha256"])}. This hash does not describe the filtered fixture bytes.</p></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        root = Path(__file__).resolve().parents[1] / "out"
        destination = args.output_dir.resolve()
        require(destination == root or root in destination.parents, "Output directory must be under repository out/")
        report = analyse(json.loads(args.input.read_text(encoding="utf-8")))
        json_text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        html_text = render(report)
        destination.mkdir(parents=True, exist_ok=True)
        json_path = destination / "bus-timing-report.json"
        html_path = destination / "bus-timing-report.html"
        json_path.write_text(json_text, encoding="utf-8")
        html_path.write_text(html_text, encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        print(f"Bus timing report failed: {exc}. No successful new report; older outputs may be stale.", file=sys.stderr)
        return 1
    print(f"Generated {json_path} and {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
