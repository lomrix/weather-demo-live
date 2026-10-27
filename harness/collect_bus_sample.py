"""Bounded SIRI bus capture with offline dry-run and synthetic replay modes."""

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ENDPOINT = "https://api.entur.io/realtime/v1/rest/et?datasetId=INN&maxSize=100"
CLIENT = "lomrix-weather-demo-live"
ACCEPT = "application/xml"
TIMEOUT = 20
MAX_BODY = 5 * 1024 * 1024
COOLDOWN = 60
SIRI = "http://www.siri.org.uk/siri"
QUAYS = {
    "NSR:Quay:101673": "Storhamarsenteret", "NSR:Quay:18003": "Storhamarsenteret",
    "NSR:Quay:17861": "Hamar skysstasjon", "NSR:Quay:101587": "Hamar skysstasjon",
    "NSR:Quay:17900": "CC Hamar", "NSR:Quay:17901": "CC Hamar",
}
ATTRIBUTION = "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS."
LICENCE = "https://data.norge.no/nlod/no/2.0"
SCHEMA_VERSION = "bus-collection-1"
ROOT = Path(__file__).resolve().parents[1]
STAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


class CollectionError(ValueError):
    def __init__(self, message, status=None, headers=None, response_byte_count=None,
                 response_sha256=None, received_at=None):
        super().__init__(message)
        self.status = status
        self.headers = headers or {}
        self.response_byte_count = response_byte_count
        self.response_sha256 = response_sha256
        self.received_at = received_at


def utc(now):
    value = now() if callable(now) else now
    if value is None:
        value = datetime.now(timezone.utc)
    return value.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def stamp(value, label):
    if type(value) is not str or not STAMP_RE.fullmatch(value):
        raise CollectionError("Malformed timezone-bearing " + label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CollectionError("Malformed timezone-bearing " + label)
    if parsed.utcoffset() is None:
        raise CollectionError("Timezone required for " + label)
    return value


def local(element):
    return element.tag.rsplit("}", 1)[-1] if "}" in element.tag else element.tag


def children(element, name):
    return [child for child in list(element) if child.tag == "{" + SIRI + "}" + name]


def one(element, name, required=True):
    found = children(element, name)
    if len(found) > 1:
        raise CollectionError("Duplicate " + name)
    if not found:
        if required:
            raise CollectionError("Missing " + name)
        return None
    return found[0]


def text(element, name, required=True):
    child = one(element, name, required)
    if child is None:
        return None
    value = (child.text or "").strip()
    if required and not value:
        raise CollectionError("Empty " + name)
    return value


def bool_value(element, name):
    value = text(element, name)
    if value not in ("true", "false", "1", "0"):
        raise CollectionError(name + " must be boolean")
    return value in ("true", "1")


def scalar_call(call, name, required=False):
    value = text(call, name, required)
    return value


def parse_response(raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise CollectionError("DOCTYPE and entity declarations are not allowed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise CollectionError("Malformed XML")
    if root.tag != "{" + SIRI + "}Siri":
        raise CollectionError("Wrong SIRI namespace or envelope")
    service = one(root, "ServiceDelivery")
    root_timestamp = text(root, "ResponseTimestamp", False)
    if root_timestamp:
        root_timestamp = stamp(root_timestamp, "ResponseTimestamp")
    status = text(service, "Status", False)
    if status == "false":
        raise CollectionError("Provider service status is false")
    if status not in (None, "true"):
        raise CollectionError("Invalid provider service status")
    if one(service, "ErrorCondition", False) is not None:
        raise CollectionError("Provider service reported an error")
    deliveries = children(service, "EstimatedTimetableDelivery")
    if not deliveries:
        raise CollectionError("Missing EstimatedTimetableDelivery")
    frames = []
    provider_timestamps = []
    more_data = []
    if root_timestamp:
        provider_timestamps.append({"location": "root", "value": root_timestamp})
    service_timestamp = text(service, "ResponseTimestamp", False)
    if service_timestamp:
        provider_timestamps.append({"location": "service_delivery", "value": stamp(service_timestamp, "ResponseTimestamp")})
    for delivery_index, delivery in enumerate(deliveries):
        delivery_status = text(delivery, "Status", False)
        if delivery_status == "false":
            raise CollectionError("Provider delivery status is false")
        if delivery_status not in (None, "true"):
            raise CollectionError("Invalid provider delivery status")
        if one(delivery, "ErrorCondition", False) is not None:
            raise CollectionError("Provider delivery reported an error")
        value = text(delivery, "ResponseTimestamp", False)
        if value:
            provider_timestamps.append({"location": f"delivery[{delivery_index}]", "value": stamp(value, "ResponseTimestamp")})
        indicator = text(delivery, "MoreData", False)
        if indicator is not None and indicator not in ("true", "false", "1", "0"):
            raise CollectionError("MoreData must be boolean")
        more_data.append({"location": f"delivery[{delivery_index}]", "value": None if indicator is None else indicator in ("true", "1")})
        current = children(delivery, "EstimatedJourneyVersionFrame")
        if not current:
            raise CollectionError("Missing EstimatedJourneyVersionFrame")
        frames.extend(current)
    journeys = []
    for frame_index, frame in enumerate(frames):
        current = children(frame, "EstimatedVehicleJourney")
        if not current:
            raise CollectionError("Missing EstimatedVehicleJourney")
        for journey_index, journey in enumerate(current):
            journeys.append((frame_index, journey_index, journey))
    if len(journeys) > 100:
        raise CollectionError("More than 100 returned journeys")
    return journeys, provider_timestamps, more_data


def has_selected_call(journey):
    for group in ("RecordedCalls", "EstimatedCalls"):
        container = one(journey, group, False)
        if container is None:
            continue
        singular = "RecordedCall" if group == "RecordedCalls" else "EstimatedCall"
        for call in children(container, singular):
            stop = one(call, "StopPointRef", False)
            if stop is not None and (stop.text or "").strip() in QUAYS:
                return True
    return False


def project_journey(frame_index, journey_index, journey):
    line = text(journey, "LineRef")
    if not line or not line.startswith("INN:Line:"):
        raise CollectionError("Invalid line identity")
    published = text(journey, "PublishedLineName")
    direction = text(journey, "DirectionRef")
    recorded = text(journey, "RecordedAtTime")
    stamp(recorded, "RecordedAtTime")
    framed = one(journey, "FramedVehicleJourneyRef")
    service_date = text(framed, "DataFrameRef")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", service_date):
        raise CollectionError("Invalid service date")
    try:
        datetime.strptime(service_date, "%Y-%m-%d")
    except ValueError:
        raise CollectionError("Invalid service date")
    journey_ref = text(framed, "DatedVehicleJourneyRef")
    result = {
        "line_ref": line, "published_name": published, "direction_ref": direction,
        "service_date": service_date, "journey_ref": journey_ref, "recorded_at_time": recorded,
    }
    for name in ("Cancellation", "Monitored"):
        if one(journey, name, False) is not None:
            result[name.lower()] = bool_value(journey, name)
    calls = []
    for group in ("RecordedCalls", "EstimatedCalls"):
        container = one(journey, group, False)
        if container is None:
            continue
        singular = "RecordedCall" if group == "RecordedCalls" else "EstimatedCall"
        for call in children(container, singular):
            quay = text(call, "StopPointRef")
            if quay not in QUAYS:
                continue
            name = text(call, "StopPointName")
            if name != QUAYS[quay]:
                raise CollectionError("Mismatched selected quay name")
            order_text = text(call, "Order")
            try:
                order = int(order_text)
            except ValueError:
                raise CollectionError("Invalid stop order")
            if order <= 0:
                raise CollectionError("Invalid stop order")
            projected = {"group": group, "quay_id": quay, "quay_name": name, "order": order}
            for name in ("AimedArrivalTime", "AimedDepartureTime", "ActualArrivalTime",
                         "ActualDepartureTime", "ExpectedArrivalTime", "ExpectedDepartureTime"):
                value = scalar_call(call, name, False)
                if value is not None:
                    projected[name] = stamp(value, name)
            for name in ("Cancellation", "Monitored"):
                if one(call, name, False) is not None:
                    projected[name.lower()] = bool_value(call, name)
            calls.append(projected)
    return result, calls


def normalized_snapshot(raw, synthetic, execution_time, observed_status=None):
    journeys, provider_timestamps, more_data = parse_response(raw)
    retained = []
    seen_journeys = set()
    seen_calls = set()
    excluded = 0
    for frame_index, journey_index, journey in journeys:
        if not has_selected_call(journey):
            excluded += 1
            continue
        projected, calls = project_journey(frame_index, journey_index, journey)
        if not calls:
            excluded += 1
            continue
        journey_key = (projected["service_date"], projected["journey_ref"])
        if journey_key in seen_journeys:
            raise CollectionError("Duplicate selected journey identity")
        seen_journeys.add(journey_key)
        orders = set()
        selected_calls = []
        for call in calls:
            call_key = (journey_key, call["group"], call["quay_id"], call["order"])
            if call_key in seen_calls or call["order"] in orders:
                raise CollectionError("Duplicate selected call identity")
            seen_calls.add(call_key)
            orders.add(call["order"])
            selected_calls.append(call)
        projected["calls"] = selected_calls
        retained.append(projected)
    snapshot = {
        "schema_version": SCHEMA_VERSION, "synthetic": synthetic,
        "execution_time_utc": iso(execution_time),
        "journeys": retained,
        "provider_timestamps": provider_timestamps,
        "more_data": more_data,
        "selection": {"quays": QUAYS, "returned_journey_count": len(journeys),
                      "excluded_journey_count": excluded, "retained_journey_count": len(retained),
                      "retained_call_count": sum(len(item["calls"]) for item in retained)},
        "attribution": ATTRIBUTION, "licence_url": LICENCE, "modified": True,
        "limitations": [
            "One bounded first page, not full-city or full-day coverage; MoreData is not inferred.",
            "Filtered public quays only; absence is unknown and predictions are not actual departures.",
            "Repeated samples may overlap; no passenger impacts or recurring reliability findings are established.",
        ],
    }
    if observed_status is not None:
        snapshot["synthetic_transport_status"] = observed_status
    return snapshot


def safe_headers(headers):
    result = {}
    for key in ("Content-Type", "Date", "Retry-After"):
        value = headers.get(key)
        if value is not None:
            result[key.lower().replace("-", "_")] = value
    return result


def transport_live(now=None):
    if os.environ.get("BUS_COLLECTION_BLOCK_NETWORK") == "1":
        raise CollectionError("Network blocked by offline verifier")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, new):
            raise CollectionError("Redirect rejected")
    request = urllib.request.Request(ENDPOINT, headers={"ET-Client-Name": CLIENT, "Accept": ACCEPT})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=TIMEOUT)
        status, headers = response.status, response.headers
        try:
            raw = response.read(MAX_BODY + 1)
        finally:
            response.close()
        received_at = utc(now)
    except urllib.error.HTTPError as error:
        headers = error.headers
        status = error.code
        error.close()
        if status in (429, 503):
            raise CollectionError("HTTP " + str(status), status, safe_headers(headers), received_at=utc(now))
        raise CollectionError("HTTP status " + str(status), status, safe_headers(headers), received_at=utc(now))
    except urllib.error.URLError:
        raise CollectionError("Network operation failed", received_at=utc(now))
    except TimeoutError:
        raise CollectionError("Network operation timed out", received_at=utc(now))
    if len(raw) > MAX_BODY:
        raise CollectionError("Response body exceeds 5 MiB", status, safe_headers(headers),
                              response_byte_count=len(raw), response_sha256=None,
                              received_at=received_at)
    if status != 200:
        raise CollectionError("HTTP status " + str(status), status, safe_headers(headers),
                              response_byte_count=len(raw), response_sha256=sha256(raw).hexdigest(),
                              received_at=received_at)
    content_type = headers.get("Content-Type", "").lower()
    if not (content_type.startswith("application/xml") or content_type.startswith("text/xml")):
        raise CollectionError("Unsupported response content type", status, safe_headers(headers),
                              response_byte_count=len(raw), response_sha256=sha256(raw).hexdigest(),
                              received_at=received_at)
    return raw, status, safe_headers(headers)


def atomic_write(path, data):
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def run(mode, response_file=None, output_root=None, transport=None, now=None):
    start = utc(now)
    output_root = Path(output_root or ROOT / "out/bus-collection")
    if mode == "dry-run":
        print(json.dumps({"mode": mode, "endpoint": ENDPOINT, "headers": {"ET-Client-Name": CLIENT, "Accept": ACCEPT},
                          "scope": "one bounded INN first page; six selected public quays", "request_limit": 1,
                          "size_limit_bytes": MAX_BODY, "timeout_seconds": TIMEOUT,
                          "destination": str(output_root), "network_calls": 0, "filesystem_mutations": 0}))
        return 0
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = output_root / ".live.lock"
    lock_fd = None
    run_dir = None
    manifest = None
    raw = None
    status = None
    headers = {}
    retrieved_at = None
    snapshot_path = None
    snapshot_temp = None
    try:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise CollectionError("Local lock is held; retry after the current run releases it")
        cooldown_path = output_root / ".live-cooldown"
        if mode == "live" and cooldown_path.exists():
            allowed = float(cooldown_path.read_text(encoding="ascii"))
            if start.timestamp() < allowed:
                raise CollectionError("Live cooldown active until " + datetime.fromtimestamp(allowed, timezone.utc).isoformat())
        run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=output_root))
        synthetic = mode == "replay"
        if mode == "replay":
            if response_file is None:
                raise CollectionError("Replay requires --response-file")
            try:
                raw = Path(response_file).read_bytes()
            except OSError:
                raise CollectionError("Replay response file could not be read")
        elif mode == "live":
            cooldown = start.timestamp() + COOLDOWN
            atomic_write(cooldown_path, str(cooldown).encode("ascii"))
            try:
                if transport is None:
                    raw, status, headers = transport_live(now)
                else:
                    raw, status, headers = transport()
                retrieved_at = utc(now)
            except CollectionError as error:
                status, headers = error.status, error.headers
                retrieved_at = error.received_at or utc(now)
                if status in (429, 503) and "retry_after" in headers:
                    try:
                        retry = parsedate_to_datetime(headers["retry_after"]).timestamp()
                    except (TypeError, ValueError, OverflowError):
                        try:
                            retry = retrieved_at.timestamp() + int(headers["retry_after"])
                        except (TypeError, ValueError):
                            retry = cooldown
                    atomic_write(cooldown_path, str(max(cooldown, retry)).encode("ascii"))
                raise
        snapshot = normalized_snapshot(raw, synthetic, start, status if synthetic else None)
        snapshot_bytes = (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        snapshot_digest = sha256(snapshot_bytes).hexdigest()
        snapshot_path = run_dir / "snapshot.json"
        snapshot_temp = snapshot_path.with_name(".snapshot.json.tmp")
        snapshot_temp.write_bytes(snapshot_bytes)
        manifest = {
            "schema_version": SCHEMA_VERSION, "mode": mode, "synthetic": synthetic,
            "execution_started_utc": iso(start), "execution_finished_utc": iso(utc(now)),
            "retrieved_at_utc": None if synthetic else iso(retrieved_at),
            "endpoint": ENDPOINT, "client_identifier": CLIENT, "accept": ACCEPT,
            "http_status": status, "response_headers": headers, "response_byte_count": len(raw),
            "response_sha256": sha256(raw).hexdigest(), "snapshot_sha256": snapshot_digest,
            "provider_timestamps": snapshot["provider_timestamps"],
            "returned_journey_count": snapshot["selection"]["returned_journey_count"],
            "retained_journey_count": snapshot["selection"]["retained_journey_count"],
            "retained_call_count": snapshot["selection"]["retained_call_count"],
            "excluded_journey_count": snapshot["selection"]["excluded_journey_count"],
            "line_refs": sorted({item["line_ref"] for item in snapshot["journeys"]}),
            "selection": snapshot["selection"], "more_data": snapshot["more_data"],
            "attribution": ATTRIBUTION, "licence_url": LICENCE, "modified": True,
            "status": "success" if snapshot["journeys"] else "empty_success",
            "failure_reason": None,
            "limitations": snapshot["limitations"],
        }
        atomic_write(run_dir / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        os.replace(snapshot_temp, snapshot_path)
        snapshot_temp = None
        print("RUN_DIRECTORY " + str(run_dir))
        return 0
    except (CollectionError, OSError, ValueError, TypeError, OverflowError) as error:
        if snapshot_temp is not None:
            try:
                snapshot_temp.unlink()
            except FileNotFoundError:
                pass
        if snapshot_path is not None:
            try:
                snapshot_path.unlink()
            except FileNotFoundError:
                pass
        if run_dir is None:
            run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=output_root))
        manifest = {
            "schema_version": SCHEMA_VERSION, "mode": mode, "synthetic": mode == "replay",
            "execution_started_utc": iso(start), "execution_finished_utc": iso(utc(now)),
            "retrieved_at_utc": None if retrieved_at is None else iso(retrieved_at), "endpoint": ENDPOINT, "client_identifier": CLIENT,
            "accept": ACCEPT, "http_status": getattr(error, "status", None) if getattr(error, "status", None) is not None else status,
            "response_headers": getattr(error, "headers", {}) or headers,
            "response_byte_count": getattr(error, "response_byte_count", None)
            if getattr(error, "response_byte_count", None) is not None else (len(raw) if raw is not None else None),
            "response_sha256": getattr(error, "response_sha256", None)
            if getattr(error, "response_sha256", None) is not None
            else (sha256(raw).hexdigest() if raw is not None and getattr(error, "response_byte_count", None) is None else None),
            "status": "failed", "failure_reason": str(error) or "Collection failed", "attribution": ATTRIBUTION,
            "licence_url": LICENCE, "modified": True,
            "limitations": ["One bounded first page, not full-city or full-day coverage."],
        }
        try:
            atomic_write(run_dir / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
        except OSError as write_error:
            print("ERROR: failed to write failure manifest", file=sys.stderr)
            return 1
        print("RUN_DIRECTORY " + str(run_dir))
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run", "replay", "live"), default="dry-run")
    parser.add_argument("--response-file", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("out/bus-collection"))
    args = parser.parse_args()
    return run(args.mode, args.response_file, args.output_root)


if __name__ == "__main__":
    sys.exit(main())
