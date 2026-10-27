"""Offline route inventory from a strictly filtered, saved Entur sample."""
import argparse
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import sys

QUAYS = {
    "NSR:Quay:101673": "Storhamarsenteret", "NSR:Quay:18003": "Storhamarsenteret",
    "NSR:Quay:17861": "Hamar skysstasjon", "NSR:Quay:101587": "Hamar skysstasjon",
    "NSR:Quay:17900": "CC Hamar", "NSR:Quay:17901": "CC Hamar",
}
TIMES = tuple(a + b + "Time" for a in ("Aimed", "Actual", "Expected") for b in ("Arrival", "Departure"))
CATEGORIES = ("actual", "prediction_only", "unknown", "cancelled")
LIMITS = [
    "Saved 21 October snapshot: one bounded first page of 100 INN journeys; no fresh collection.",
    "Only six quays at three selected stops; no complete city/day coverage. Absence from this subset is not absence of a route/service.",
    "Predictions are separate from actuals; missing data is unknown. RecordedCalls alone never proves an actual departure.",
    "Provider actuals are not independently verified physical events. Counts are not passenger counts.",
    "No recurring patterns, causes, route performance ranking or demonstrated municipal benefit.",
]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def schema(obj, required, optional=()):
    require(type(obj) is dict, "Expected object")
    require(set(required) <= obj.keys(), "Missing required fields: " + str(set(required) - obj.keys()))
    require(obj.keys() <= set(required) | set(optional), "Unexpected fields: " + str(obj.keys() - set(required) - set(optional)))


def text(value):
    require(type(value) is str and bool(value.strip()), "Expected non-empty string")
    return value


def scalar(obj):
    schema(obj, ["value"])
    return text(obj["value"])


def name(values):
    require(type(values) is list and len(values) == 1, "Expected single name list")
    return scalar(values[0])


def stamp(value):
    text(value)
    require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value)), "Malformed timestamp: " + value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None, "Timestamp requires timezone")
    return parsed


def flags(obj):
    for key in ("Cancellation", "Monitored"):
        if key in obj:
            require(type(obj[key]) is bool, key + " must be boolean")
    return obj.get("Cancellation", False)


def analyse(saved, digest):
    metadata = ["source_url", "client_identifier", "retrieved_at_utc", "http_status", "server_date", "response_sha256", "attribution", "licence_url", "modified", "selection"]
    schema(saved, metadata + ["journeys"])
    require(saved["source_url"] == "https://api.entur.io/realtime/v1/rest/et?datasetId=INN&maxSize=100", "Invalid source URL")
    require(type(saved["http_status"]) is int and saved["http_status"] == 200, "HTTP status must be 200")
    require(stamp(saved["retrieved_at_utc"]).utcoffset().total_seconds() == 0, "Retrieval time must be UTC")
    require(parsedate_to_datetime(text(saved["server_date"])).utcoffset() is not None, "Invalid server date timezone")
    for key in ("client_identifier", "attribution"):
        text(saved[key])
    require(bool(re.fullmatch(r"[0-9a-f]{64}", text(saved["response_sha256"]))), "Invalid original response hash")
    require(saved["licence_url"] == "https://data.norge.no/nlod/no/2.0", "Invalid licence URL")
    require(saved["modified"] is True, "Modified selection must be disclosed")
    selection = saved["selection"]
    schema(selection, ["quays", "description", "original_page_journey_count", "complete_hamar_coverage"])
    require(selection["quays"] == QUAYS, "Invalid approved quay mapping or names")
    text(selection["description"])
    require(type(selection["original_page_journey_count"]) is int and selection["original_page_journey_count"] == 100, "Expected bounded page of 100 journeys")
    require(selection["complete_hamar_coverage"] is False, "Coverage must be partial")
    require(type(saved["journeys"]) is list and 0 < len(saved["journeys"]) <= 100, "Invalid journey list")
    routes, identities, dates = {}, set(), set()
    for journey in saved["journeys"]:
        schema(journey, ["RecordedAtTime", "LineRef", "DirectionRef", "FramedVehicleJourneyRef", "PublishedLineName"], ["Cancellation", "Monitored", "RecordedCalls", "EstimatedCalls"])
        stamp(journey["RecordedAtTime"])
        line, published = scalar(journey["LineRef"]), name(journey["PublishedLineName"])
        require(bool(re.fullmatch(r"INN:Line:[^\s:]+", line)), "Invalid LineRef")
        scalar(journey["DirectionRef"])
        framed = journey["FramedVehicleJourneyRef"]
        schema(framed, ["DataFrameRef", "DatedVehicleJourneyRef"])
        day = scalar(framed["DataFrameRef"])
        require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)), "Invalid service date")
        date.fromisoformat(day)
        dates.add(day)
        jid = text(framed["DatedVehicleJourneyRef"])
        require(bool(re.fullmatch(r"INN:ServiceJourney:[^\s:]+", jid)), "Invalid journey identifier")
        require((day, jid) not in identities, "Duplicate journey or contradictory identity")
        identities.add((day, jid))
        cancelled = flags(journey)
        route = routes.setdefault(line, dict(line_ref=line, published_name=published, journeys=0, calls=0, **dict.fromkeys(CATEGORIES, 0)))
        require(route["published_name"] == published, "Conflicting published name for LineRef")
        route["journeys"] += 1
        orders, count = set(), 0
        for group, singular in (("RecordedCalls", "RecordedCall"), ("EstimatedCalls", "EstimatedCall")):
            if group not in journey:
                continue
            schema(journey[group], [singular])
            records = journey[group][singular]
            require(type(records) is list, "Call group must be list")
            for call in records:
                schema(call, ["StopPointRef", "StopPointName", "Order"], ["Cancellation", *TIMES])
                quay = scalar(call["StopPointRef"])
                require(quay in QUAYS and name(call["StopPointName"]) == QUAYS[quay], "Unknown quay or mismatched quay/name")
                order = call["Order"]
                require(type(order) is int and order > 0, "Order must be positive integer")
                require(order not in orders, "Duplicate call or contradictory call identity")
                orders.add(order)
                call_cancelled = flags(call)
                for key in TIMES:
                    if key in call:
                        stamp(call[key])
                category = "unknown"
                if cancelled or call_cancelled:
                    category = "cancelled"
                elif "AimedDepartureTime" in call and "ActualDepartureTime" in call:
                    category = "actual"
                elif "AimedDepartureTime" in call and "ExpectedDepartureTime" in call and "ActualDepartureTime" not in call:
                    category = "prediction_only"
                route[category] += 1
                route["calls"] += 1
                count += 1
        require(count > 0, "Journey has no selected calls")
    rows = sorted(routes.values(), key=lambda row: row["line_ref"])
    for row in rows:
        row["actual_data_availability"] = "Actual comparisons available" if row["actual"] else "No actual comparisons in this sample; not proof of poor service"
    return dict(title="Saved 21 October snapshot at three Hamar stops", source={key: saved[key] for key in metadata}, input_sha256=digest, service_dates=sorted(dates), routes=rows, totals={key: sum(row[key] for row in rows) for key in ("journeys", "calls", *CATEGORIES)}, interpretation_limits=LIMITS)


def render(report):
    columns = ("line_ref", "published_name", "journeys", "calls", *CATEGORIES, "actual_data_availability")
    e = lambda value: escape(str(value), quote=True)
    rows = "".join("<tr>" + "".join("<td>" + e(row[key]) + "</td>" for key in columns) + "</tr>" for row in report["routes"])
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>' + e(report["title"]) + '</title><body><h1>' + e(report["title"]) + '</h1><p>Coverage inventory; availability is separate from performance.</p><table border="1"><caption>Selected route observations</caption><thead><tr>' + ''.join('<th scope="col">' + e(key) + '</th>' for key in columns) + '</tr></thead><tbody>' + rows + '</tbody></table><h2>Totals</h2><pre>' + e(json.dumps(report["totals"], indent=2)) + '</pre><h2>Interpretation limits</h2><ul>' + ''.join('<li>' + e(item) + '</li>' for item in LIMITS) + '</ul><h2>Provenance, service dates and approved quays</h2><pre>' + e(json.dumps({key: report[key] for key in ("source", "service_dates", "input_sha256")}, ensure_ascii=False, indent=2)) + '</pre></body></html>\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        report = analyse(json.loads(raw.decode("utf-8")), sha256(raw).hexdigest())
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        html = render(report)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "route-coverage.json").write_text(encoded, encoding="utf-8")
        (args.output_dir / "route-coverage.html").write_text(html, encoding="utf-8")
    except (ValueError, KeyError, TypeError, OSError, AttributeError, OverflowError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    print(str(args.output_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
