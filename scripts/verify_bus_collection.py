"""Independent offline checks for the bounded bus collector."""

import copy
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import collect_bus_sample as collector


def xml_source(prefix="s", selected=True, malformed=False, extra=False):
    selected_call = """
      <s:EstimatedCall>
        <s:StopPointRef>NSR:Quay:101673</s:StopPointRef>
        <s:StopPointName>Storhamarsenteret</s:StopPointName>
        <s:Order>1</s:Order>
        <s:AimedDepartureTime>2026-10-27T10:00:00+02:00</s:AimedDepartureTime>
        <s:ExpectedDepartureTime>2026-10-27T10:02:00+02:00</s:ExpectedDepartureTime>
      </s:EstimatedCall>""" if selected else """
      <s:EstimatedCall><s:StopPointRef>NSR:Quay:999</s:StopPointRef>
      <s:StopPointName>Elsewhere</s:StopPointName><s:Order>1</s:Order></s:EstimatedCall>"""
    second = """
      <s:EstimatedVehicleJourney>
        <s:LineRef>INN:Line:22</s:LineRef><s:PublishedLineName>B22</s:PublishedLineName>
        <s:DirectionRef>outbound</s:DirectionRef><s:RecordedAtTime>2026-10-27T08:00:00Z</s:RecordedAtTime>
        <s:FramedVehicleJourneyRef><s:DataFrameRef>2026-10-27</s:DataFrameRef>
        <s:DatedVehicleJourneyRef>INN:ServiceJourney:22</s:DatedVehicleJourneyRef></s:FramedVehicleJourneyRef>
        <s:RecordedCalls><s:RecordedCall><s:StopPointRef>NSR:Quay:17861</s:StopPointRef>
        <s:StopPointName>Hamar skysstasjon</s:StopPointName><s:Order>2</s:Order>
        <s:ActualArrivalTime>2026-10-27T10:05:00+02:00</s:ActualArrivalTime></s:RecordedCall></s:RecordedCalls>
      </s:EstimatedVehicleJourney>""" if extra else ""
    body = f"""<{prefix}:Siri xmlns:{prefix}="http://www.siri.org.uk/siri"><{prefix}:ServiceDelivery>
    <{prefix}:Status>true</{prefix}:Status><{prefix}:EstimatedTimetableDelivery>
    <{prefix}:ResponseTimestamp>2026-10-27T08:00:00Z</{prefix}:ResponseTimestamp>
    <{prefix}:MoreData>false</{prefix}:MoreData><{prefix}:EstimatedJourneyVersionFrame>
    <{prefix}:EstimatedVehicleJourney><{prefix}:LineRef>INN:Line:21</{prefix}:LineRef>
    <{prefix}:PublishedLineName>B21</{prefix}:PublishedLineName><{prefix}:DirectionRef>outbound</{prefix}:DirectionRef>
    <{prefix}:RecordedAtTime>2026-10-27T08:00:00Z</{prefix}:RecordedAtTime>
    <{prefix}:FramedVehicleJourneyRef><{prefix}:DataFrameRef>2026-10-27</{prefix}:DataFrameRef>
    <{prefix}:DatedVehicleJourneyRef>INN:ServiceJourney:21</{prefix}:DatedVehicleJourneyRef></{prefix}:FramedVehicleJourneyRef>
    <{prefix}:EstimatedCalls>{selected_call}</{prefix}:EstimatedCalls></{prefix}:EstimatedVehicleJourney>{second}
    </{prefix}:EstimatedJourneyVersionFrame></{prefix}:EstimatedTimetableDelivery>
    </{prefix}:ServiceDelivery></{prefix}:Siri>"""
    return body.replace("<s:", "<" + prefix + ":").replace("</s:", "</" + prefix + ":").encode()


def write(path, data):
    path.write_bytes(data)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    os.environ["BUS_COLLECTION_BLOCK_NETWORK"] = "1"
    parent = ROOT / "out/bus-collection-verification"
    parent.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="checks-", dir=parent))
    cases = []

    def case(name, check):
        record = {"case": name, "passed": False}
        try:
            check(record)
            record["passed"] = True
        except (AssertionError, OSError, ValueError, KeyError, ET.ParseError) as error:
            record["failure"] = str(error)
        cases.append(record)
        print(("PASS: " if record["passed"] else "FAIL: ") + name)

    def assert_true(value, message):
        if not value:
            raise AssertionError(message)

    def replay(name, raw):
        root = run / name
        source = root / "source.xml"
        root.mkdir(parents=True, exist_ok=True)
        write(source, raw)
        result = collector.run("replay", source, root / "output")
        assert_true(result == 0, "replay exit")
        run_dirs = list((root / "output").glob("run-*"))
        assert_true(len(run_dirs) == 1, "unique run directory")
        return run_dirs[0], read(run_dirs[0] / "snapshot.json"), read(run_dirs[0] / "manifest.json")

    def dry(record):
        root = run / "dry-root"
        output = collector.run("dry-run", output_root=root)
        assert_true(output == 0 and not root.exists(), "dry-run has no filesystem mutation")
    case("dry-run-no-network-or-files", dry)

    def cli_dry(record):
        root = run / "cli-dry-root"
        result = subprocess.run(
            [sys.executable, str(ROOT / "harness/collect_bus_sample.py"), "--output-root", str(root)],
            cwd=ROOT, shell=False, capture_output=True, text=True, encoding="utf-8", timeout=30,
            env={**os.environ, "BUS_COLLECTION_BLOCK_NETWORK": "1"})
        assert_true(result.returncode == 0 and not root.exists(), "default CLI dry-run is mutation-free")
        record["stdout"], record["stderr"], record["exit_code"] = result.stdout, result.stderr, result.returncode
    case("cli-default-dry-run", cli_dry)

    def cli_timestamp(record):
        root = run / "cli-timestamp"
        source = root / "source.xml"
        root.mkdir(parents=True, exist_ok=True)
        write(source, xml_source().replace(b"2026-10-27T10:02:00+02:00", b"2026-02-30T10:02:00+02:00"))
        result = subprocess.run(
            [sys.executable, str(ROOT / "harness/collect_bus_sample.py"), "--mode", "replay",
             "--response-file", str(source), "--output-root", str(root / "output")],
            cwd=ROOT, shell=False, capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert_true(result.returncode == 1, "CLI rejects impossible timestamp")
        output = next((root / "output").glob("run-*"))
        failure = read(output / "manifest.json")["failure_reason"]
        assert_true("Malformed timezone-bearing ExpectedDepartureTime" in failure and "2026-02-30" not in failure,
                    "sanitized timestamp failure")
        assert_true(not (output / "snapshot.json").exists() and "Traceback" not in result.stderr,
                    "no snapshot or traceback")
        record["stdout"] = result.stdout
        record["stderr"] = result.stderr
        record["exit_code"] = result.returncode
    case("cli-impossible-timestamp", cli_timestamp)

    def valid(record):
        raw = xml_source(extra=True).replace(
            b'<s:Siri xmlns:s="http://www.siri.org.uk/siri">',
            b'<s:Siri xmlns:s="http://www.siri.org.uk/siri"><s:ResponseTimestamp>2026-10-27T07:59:00Z</s:ResponseTimestamp>',
            1).replace(
            b"<s:ServiceDelivery>", b"<s:ServiceDelivery><s:ResponseTimestamp>2026-10-27T07:59:30Z</s:ResponseTimestamp>",
            1)
        directory, snapshot, manifest = replay("valid", raw)
        assert_true(snapshot["synthetic"] and len(snapshot["journeys"]) == 2, "synthetic multi-line snapshot")
        assert_true(snapshot["selection"]["retained_call_count"] == 2, "selected calls retained")
        assert_true(manifest["response_sha256"] != manifest["snapshot_sha256"], "distinct hashes")
        assert_true(manifest["status"] == "success" and manifest["http_status"] is None, "honest replay status")
        assert_true({item["location"] for item in snapshot["provider_timestamps"]} ==
                    {"root", "service_delivery", "delivery[0]"}, "all provider timestamp locations")
        assert_true("VehicleRef" not in directory.joinpath("snapshot.json").read_text(), "projection excludes vehicle fields")
    case("valid-replay-and-projection", valid)

    def formatting(record):
        _, first, first_manifest = replay("format-one", xml_source("s"))
        _, second, second_manifest = replay("format-two", xml_source("x").replace(b"\n", b"\n  "))
        assert_true(first["journeys"] == second["journeys"], "formatting/prefix independent selected data")
        assert_true(first_manifest["response_sha256"] != second_manifest["response_sha256"], "raw hashes differ")
    case("formatting-variation", formatting)

    for name, raw in (
        ("wrong-envelope", b"<x/>"),
        ("malformed", b"<s:Siri"),
        ("doctype", b"<!DOCTYPE x><s:Siri xmlns:s=\"http://www.siri.org.uk/siri\"/>"),
    ):
        def rejected(record, name=name, raw=raw):
            root = run / name
            source = root / "source.xml"
            root.mkdir(parents=True, exist_ok=True)
            write(source, raw)
            assert_true(collector.run("replay", source, root / "output") == 1, "invalid XML rejected")
            output = next((root / "output").glob("run-*"))
            assert_true(read(output / "manifest.json")["status"] == "failed", "failed manifest")
            assert_true(not (output / "snapshot.json").exists(), "no snapshot on failure")
        case(name, rejected)

    def failed_status(record):
        raw = xml_source().replace(b"<s:Status>true</s:Status>", b"<s:Status>false</s:Status>")
        directory = run / "failed-status"
        source = directory / "source.xml"
        directory.mkdir(parents=True, exist_ok=True)
        write(source, raw)
        assert_true(collector.run("replay", source, directory / "output") == 1, "status rejection")
        output = next((directory / "output").glob("run-*"))
        manifest = read(output / "manifest.json")
        assert_true(manifest["status"] == "failed" and not (output / "snapshot.json").exists(), "failed manifest only")
    case("failed-service-status", failed_status)

    for name, marker in (("failed-delivery-status", b"<s:Status>false</s:Status>"),
                         ("delivery-error", b"<s:ErrorCondition><s:Description>secret</s:Description></s:ErrorCondition>")):
        def delivery_failure(record, name=name, marker=marker):
            raw = xml_source().replace(b"<s:EstimatedTimetableDelivery>", b"<s:EstimatedTimetableDelivery>" + marker)
            root = run / name
            source = root / "source.xml"
            root.mkdir(parents=True, exist_ok=True)
            write(source, raw)
            output_root = root / "output"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                result = collector.run("replay", source, output_root)
            assert_true(result == 1, "delivery failure rejected")
            output = next(output_root.glob("run-*"))
            text = (output / "manifest.json").read_text(encoding="utf-8") + captured.getvalue()
            assert_true("secret" not in text and not (output / "snapshot.json").exists(), "safe delivery failure")
        case(name, delivery_failure)

    def empty(record):
        _, snapshot, manifest = replay("empty", xml_source(selected=False))
        assert_true(manifest["status"] == "empty_success" and snapshot["journeys"] == [], "empty selection is success")
    case("empty-selection", empty)

    def unselected_missing_name(record):
        raw = xml_source(selected=False).replace(b"<s:StopPointName>Elsewhere</s:StopPointName>", b"")
        _, snapshot, manifest = replay("unselected-missing-name", raw)
        assert_true(manifest["status"] == "empty_success" and snapshot["selection"]["excluded_journey_count"] == 1,
                    "unselected malformed call is excluded")
    case("unselected-missing-stop-name", unselected_missing_name)

    def unselected_missing_metadata(record):
        raw = xml_source(selected=False)
        for marker in (b"<s:LineRef>INN:Line:21</s:LineRef>", b"<s:PublishedLineName>B21</s:PublishedLineName>",
                       b"<s:DirectionRef>outbound</s:DirectionRef>"):
            raw = raw.replace(marker, b"")
        _, snapshot, manifest = replay("unselected-missing-metadata", raw)
        assert_true(manifest["status"] == "empty_success" and snapshot["selection"]["excluded_journey_count"] == 1,
                    "unselected journey metadata is not validated")
    case("unselected-missing-journey-metadata", unselected_missing_metadata)

    def mocked_live(record):
        root = run / "live"
        calls = []
        def transport():
            calls.append(True)
            return xml_source(extra=True), 200, {"content-type": "application/xml"}
        assert_true(collector.run("live", output_root=root, transport=transport) == 0, "mocked live success")
        assert_true(len(calls) == 1, "exactly one mocked request")
        directory = next(root.glob("run-*"))
        manifest = read(directory / "manifest.json")
        assert_true(manifest["synthetic"] is False and manifest["retrieved_at_utc"] is not None, "live labeling")
        assert_true(not (root / ".live.lock").exists(), "lock released")
    case("mocked-live-single-request", mocked_live)

    def cooldown(record):
        root = run / "cooldown"
        calls = []
        def transport():
            calls.append(True)
            return xml_source(), 200, {}
        assert_true(collector.run("live", output_root=root, transport=transport) == 0, "first live")
        assert_true(collector.run("live", output_root=root, transport=transport) == 1 and len(calls) == 1, "cooldown blocks request")
    case("cooldown-blocks-second-request", cooldown)

    def replay_no_cooldown(record):
        root = run / "replay-cooldown"
        source = root / "source.xml"
        root.mkdir(parents=True, exist_ok=True)
        write(source, xml_source())
        assert_true(collector.run("replay", source, root) == 0, "replay succeeds")
        assert_true(not (root / ".live-cooldown").exists(), "replay does not consume cooldown")
    case("replay-does-not-consume-cooldown", replay_no_cooldown)

    def preserved_projection(record):
        raw = xml_source().replace(
            b"<s:ExpectedDepartureTime>2026-10-27T10:02:00+02:00</s:ExpectedDepartureTime>",
            b"<s:ActualArrivalTime>2026-10-27T10:03:00+02:00</s:ActualArrivalTime>")
        _, snapshot, _ = replay("arrival-only", raw)
        call = snapshot["journeys"][0]["calls"][0]
        assert_true("ActualArrivalTime" in call and "ActualDepartureTime" not in call,
                    "arrival-only actual does not invent departure")
        assert_true("ExpectedDepartureTime" not in call, "missing supplied value remains absent")
    case("missing-and-arrival-only-times", preserved_projection)

    def rejected_source(record, raw, expected):
        root = run / ("reject-" + expected.replace(" ", "-"))
        source = root / "source.xml"
        root.mkdir(parents=True, exist_ok=True)
        write(source, raw)
        assert_true(collector.run("replay", source, root / "output") == 1, expected)
        output = next((root / "output").glob("run-*"))
        assert_true(expected.lower() in read(output / "manifest.json")["failure_reason"].lower(), "useful rejection")

    case("duplicate-journey", lambda record: rejected_source(
        record, xml_source() .replace(b"</s:EstimatedVehicleJourney>", b"</s:EstimatedVehicleJourney><s:EstimatedVehicleJourney><s:LineRef>INN:Line:21</s:LineRef><s:PublishedLineName>B21</s:PublishedLineName><s:DirectionRef>x</s:DirectionRef><s:RecordedAtTime>2026-10-27T08:00:00Z</s:RecordedAtTime><s:FramedVehicleJourneyRef><s:DataFrameRef>2026-10-27</s:DataFrameRef><s:DatedVehicleJourneyRef>INN:ServiceJourney:21</s:DatedVehicleJourneyRef></s:FramedVehicleJourneyRef><s:EstimatedCalls><s:EstimatedCall><s:StopPointRef>NSR:Quay:101673</s:StopPointRef><s:StopPointName>Storhamarsenteret</s:StopPointName><s:Order>1</s:Order></s:EstimatedCall></s:EstimatedCalls></s:EstimatedVehicleJourney>"), "duplicate"))

    invalid_cases = (
        ("duplicate-call", xml_source().replace(
            b"</s:EstimatedCalls>", b"<s:EstimatedCall><s:StopPointRef>NSR:Quay:101673</s:StopPointRef>"
            b"<s:StopPointName>Storhamarsenteret</s:StopPointName><s:Order>1</s:Order></s:EstimatedCall></s:EstimatedCalls>"), "duplicate"),
        ("bad-time", xml_source().replace(b"2026-10-27T10:02:00+02:00", b"not-a-time"), "expecteddeparturetime"),
        ("bad-cancellation", xml_source().replace(
            b"</s:EstimatedCall>", b"<s:Cancellation>maybe</s:Cancellation></s:EstimatedCall>"), "boolean"),
        ("bad-quay-name", xml_source().replace(b"Storhamarsenteret</s:StopPointName>", b"Wrong</s:StopPointName>"), "mismatched"),
        ("bad-date", xml_source().replace(b"<s:DataFrameRef>2026-10-27</s:DataFrameRef>",
                                          b"<s:DataFrameRef>2026-02-30</s:DataFrameRef>"), "service date"),
    )
    for name, raw, expected in invalid_cases:
        case(name, lambda record, raw=raw, expected=expected: rejected_source(record, raw, expected))

    def canaries(record):
        raw = xml_source().replace(
            b"<s:RecordedAtTime>", b"<s:VehicleRef>private</s:VehicleRef><s:OperatorRef>staff</s:OperatorRef>"
            b"<s:Notice>contact@example.invalid</s:Notice><s:RecordedAtTime>")
        directory, _, _ = replay("canaries", raw)
        saved = (directory / "snapshot.json").read_text(encoding="utf-8")
        assert_true(all(value not in saved for value in ("private", "staff", "contact@example.invalid")),
                    "unapproved source fields are not persisted")
    case("discarded-source-canaries", canaries)

    def metadata_canaries(record):
        raw = xml_source().replace(
            b'<s:Siri xmlns:s="http://www.siri.org.uk/siri">',
            b'<s:Siri xmlns:s="http://www.siri.org.uk/siri"><s:ResponseTimestamp>2026-10-27T07:59:00Z</s:ResponseTimestamp>',
            1).replace(
            b"<s:ServiceDelivery>", b"<s:ServiceDelivery><s:ResponseTimestamp>2026-10-27T07:59:30Z</s:ResponseTimestamp>",
            1).replace(b"<s:MoreData>false</s:MoreData>", b"<s:MoreData>CONTACT_CANARY@example.invalid</s:MoreData>")
        root = run / "metadata-canaries"
        source = root / "source.xml"
        root.mkdir(parents=True, exist_ok=True)
        write(source, raw)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            result = collector.run("replay", source, root / "output")
        assert_true(result == 1, "invalid MoreData rejected")
        output = next((root / "output").glob("run-*"))
        saved = "\n".join(path.read_text(encoding="utf-8") for path in output.iterdir())
        assert_true("CONTACT_CANARY" not in saved and "CONTACT_CANARY" not in captured.getvalue(),
                    "MoreData canary not persisted or logged")
    case("provider-metadata-canaries", metadata_canaries)

    def transport_failure(record):
        root = run / "transport-failure"
        def transport():
            raise collector.CollectionError("HTTP 429", 429, {"retry_after": "120"})
        assert_true(collector.run("live", output_root=root, transport=transport) == 1, "429 failure")
        output = next(root.glob("run-*"))
        manifest = read(output / "manifest.json")
        assert_true(manifest["http_status"] == 429 and manifest["response_headers"]["retry_after"] == "120", "429 metadata")
        assert_true(not (output / "snapshot.json").exists(), "no snapshot on HTTP failure")
    case("http-429-no-retry", transport_failure)

    def moving_retry_after(record):
        root = run / "moving-retry"
        clock = [__import__("datetime").datetime(2026, 10, 27, 15, 0, tzinfo=__import__("datetime").timezone.utc)]
        calls = []
        def now():
            return clock[0]
        def transport():
            calls.append(clock[0])
            clock[0] = clock[0].replace(minute=0, second=20)
            raise collector.CollectionError("HTTP 429", 429, {"retry_after": "120"}, received_at=clock[0])
        assert_true(collector.run("live", output_root=root, transport=transport, now=now) == 1, "moving Retry-After failure")
        deadline = float((root / ".live-cooldown").read_text(encoding="ascii"))
        assert_true(deadline == clock[0].timestamp() + 120, "deadline starts at receipt")
        clock[0] = clock[0].replace(minute=2, second=5)
        assert_true(collector.run("live", output_root=root, transport=transport, now=now) == 1 and len(calls) == 1,
                    "no request before receipt-based deadline")
    case("moving-retry-after-receipt", moving_retry_after)

    def received_invalid(record):
        root = run / "received-invalid"
        body = b"<not-siri />"
        def transport():
            return body, 200, {"content_type": "application/xml", "date": "Tue, 27 Oct 2026 15:00:20 GMT"}
        assert_true(collector.run("live", output_root=root, transport=transport) == 1, "invalid received body rejected")
        output = next(root.glob("run-*"))
        manifest = read(output / "manifest.json")
        assert_true(manifest["http_status"] == 200 and manifest["response_byte_count"] == len(body)
                    and manifest["response_sha256"] == __import__("hashlib").sha256(body).hexdigest()
                    and manifest["retrieved_at_utc"] is not None and not (output / "snapshot.json").exists(),
                    "received evidence preserved")
    case("received-invalid-preserves-metadata", received_invalid)

    def fake_transport(record):
        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key, default)
        class Response:
            status = 200
            headers = Headers({"Content-Type": "application/xml", "Date": "Tue, 27 Oct 2026 08:00:00 GMT"})
            def __init__(self, body):
                self.body, self.read_args, self.closed = body, None, False
            def read(self, size):
                self.read_args = size
                return self.body
            def close(self):
                self.closed = True
        response = Response(b"x" * (collector.MAX_BODY + 1))
        captured = {}
        class Opener:
            def open(self, request, timeout):
                captured.update(method=request.get_method(), url=request.full_url, headers=dict(request.header_items()),
                                timeout=timeout)
                return response
        old = collector.urllib.request.build_opener
        collector.urllib.request.build_opener = lambda handler: Opener()
        try:
            blocked = os.environ.pop("BUS_COLLECTION_BLOCK_NETWORK", None)
            try:
                collector.transport_live()
            except collector.CollectionError as error:
                assert_true(error.status == 200 and error.headers["content_type"] == "application/xml",
                            "body-limit status and headers")
                assert_true(error.response_byte_count == collector.MAX_BODY + 1 and error.response_sha256 is None,
                            "body-limit metadata")
            else:
                raise AssertionError("body-limit rejection")
        finally:
            if blocked is not None:
                os.environ["BUS_COLLECTION_BLOCK_NETWORK"] = blocked
            collector.urllib.request.build_opener = old
        request_headers = {key.lower(): value for key, value in captured["headers"].items()}
        assert_true(captured["method"] == "GET" and captured["url"] == collector.ENDPOINT
                    and captured["timeout"] == collector.TIMEOUT
                    and request_headers == {"accept": "application/xml", "et-client-name": collector.CLIENT},
                    "exact transport request")
        assert_true(response.read_args == collector.MAX_BODY + 1 and response.closed, "bounded read and close")
    case("actual-transport-body-limit", fake_transport)

    def retry_after(record):
        root = run / "retry-after"
        fixed = __import__("datetime").datetime(2026, 10, 27, 8, 0, tzinfo=__import__("datetime").timezone.utc)
        for label, value, expected in (("seconds", "120", fixed.timestamp() + 120),
                                       ("http-date", "Tue, 27 Oct 2026 08:03:00 GMT", fixed.timestamp() + 180)):
            calls = []
            def transport(value=value):
                calls.append(True)
                raise collector.CollectionError("HTTP 429", 429, {"retry_after": value})
            assert_true(collector.run("live", output_root=root / label, transport=transport, now=lambda: fixed) == 1,
                        "Retry-After failure")
            deadline = float((root / label / ".live-cooldown").read_text(encoding="ascii"))
            assert_true(deadline == expected and len(calls) == 1, "persisted Retry-After deadline")
            assert_true(collector.run("live", output_root=root / label, transport=transport, now=lambda: fixed) == 1
                        and len(calls) == 1, "no retry before deadline")
    case("retry-after-delay-and-date", retry_after)

    def publication_failure(record):
        root = run / "publication"
        source = root / "source.xml"
        root.mkdir(parents=True, exist_ok=True)
        write(source, xml_source())
        assert_true(collector.run("replay", source, root / "prior") == 0, "prior valid run")
        prior = next((root / "prior").glob("run-*"))
        before = {path.name: path.read_bytes() for path in prior.iterdir()}
        old = collector.atomic_write
        state = {"failed": False}
        def fail_once(path, data):
            if path.name == "manifest.json" and not state["failed"]:
                state["failed"] = True
                raise OSError("synthetic output failure")
            return old(path, data)
        collector.atomic_write = fail_once
        try:
            result = collector.run("replay", source, root / "failed")
        finally:
            collector.atomic_write = old
        assert_true(result == 1, "publication failure exit")
        failed = next((root / "failed").glob("run-*"))
        assert_true(not (failed / "snapshot.json").exists(), "failed run has no final snapshot")
        assert_true({path.name: path.read_bytes() for path in prior.iterdir()} == before, "prior run preserved")
    case("publication-failure-preserves-prior", publication_failure)

    def failed_transport(record):
        root = run / "transport-errors"
        for label, error in (
            ("503", collector.CollectionError("HTTP 503", 503, {"retry_after": "120"})),
            ("timeout", TimeoutError("timed out")),
            ("redirect", collector.CollectionError("Redirect rejected")),
            ("body-limit", collector.CollectionError("Response body exceeds 5 MiB")),
        ):
            def transport(error=error):
                raise error
            assert_true(collector.run("live", output_root=root / label, transport=transport) == 1, label + " failure")
            output = next((root / label).glob("run-*"))
            assert_true(not (output / "snapshot.json").exists(), label + " has no snapshot")
    case("bounded-live-failures", failed_transport)

    def missing_replay(record):
        root = run / "missing-replay"
        assert_true(collector.run("replay", root / "missing.xml", root / "output") == 1, "missing replay rejected")
        output = next((root / "output").glob("run-*"))
        assert_true(read(output / "manifest.json")["status"] == "failed", "missing replay failure manifest")
    case("missing-replay-input", missing_replay)

    def lock_failure(record):
        root = run / "held-lock"
        root.mkdir()
        (root / ".live.lock").write_text("held", encoding="ascii")
        calls = []
        def transport():
            calls.append(True)
            return xml_source(), 200, {}
        assert_true(collector.run("live", output_root=root, transport=transport) == 1 and not calls,
                    "held lock makes zero requests")
        assert_true((root / ".live.lock").exists(), "held lock preserved")
        (root / ".live.lock").unlink()
    case("held-lock-no-request", lock_failure)

    passed = sum(item["passed"] for item in cases)
    summary = {"passed": passed, "total": len(cases), "model_requests": 0, "live_requests": 0, "cases": cases}
    (run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"{'PASS' if passed == len(cases) else 'FAIL'}: {passed}/{len(cases)} offline cases; zero model/live requests")
    print(run / "summary.json")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
