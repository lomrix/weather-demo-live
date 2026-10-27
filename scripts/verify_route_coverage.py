"""Independent offline route coverage assertions using saved and synthetic inputs."""
import copy
import hashlib
from html import escape
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/hamar-route-coverage-2026-10-21.json"
HASH = "9a3076076a18e7b29338c1fb0f1c05fc196d0ba10470a66e643eceb692560e1f"
ORIGINAL = "72faadd1e586e333a1bb77f9320e56aa23a7622e7b53d6a58d12c34b697bc58d"
QUAYS = {"NSR:Quay:101673": "Storhamarsenteret", "NSR:Quay:18003": "Storhamarsenteret", "NSR:Quay:17861": "Hamar skysstasjon", "NSR:Quay:101587": "Hamar skysstasjon", "NSR:Quay:17900": "CC Hamar", "NSR:Quay:17901": "CC Hamar"}
KEYS = ("journeys", "calls", "actual", "prediction_only", "unknown", "cancelled")
ANCHORS = {"INN:Line:21": ("B21", (6, 18, 10, 8, 0, 0)), "INN:Line:22": ("B22", (3, 6, 3, 3, 0, 0)), "INN:Line:660": ("660", (1, 2, 0, 2, 0, 0))}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def calls(data):
    for journey in data["journeys"]:
        for group, singular in (("RecordedCalls", "RecordedCall"), ("EstimatedCalls", "EstimatedCall")):
            yield from journey.get(group, {}).get(singular, [])


def main():
    parent = ROOT / "out/route-coverage-verification"
    parent.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="checks-", dir=parent))
    raw = FIXTURE.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    original = json.loads(raw)
    results = []

    def case(label, mutate=None, reason=None, check=None, missing=False, preserve=False, line_ending=None):
        folder = run / label
        folder.mkdir()
        data = copy.deepcopy(original)
        if mutate:
            mutate(data)
        input_path = folder / "synthetic.json" if mutate or missing or line_ending else FIXTURE
        if mutate:
            write(input_path, data)
        elif line_ending:
            input_path.write_bytes(normalized.replace(b"\n", line_ending))
        output = folder / "report"
        if preserve:
            output.mkdir()
            for suffix in ("json", "html"):
                (output / ("route-coverage." + suffix)).write_text("earlier valid sentinel", encoding="utf-8")
        command = [sys.executable, str(ROOT / "harness/route_coverage_report.py"), "--input", str(input_path), "--output-dir", str(output)]
        result = dict(case=label, synthetic=bool(mutate or missing or line_ending), command=command, assertions=[], passed=False)

        def expect(ok, message):
            result["assertions"].append(dict(assertion=message, passed=bool(ok)))
            if not ok:
                raise AssertionError(message)

        try:
            process = subprocess.run(command, cwd=ROOT, shell=False, capture_output=True, encoding="utf-8", errors="strict", timeout=30)
            result.update(exit_code=process.returncode, stdout=process.stdout, stderr=process.stderr)
            if reason:
                expect(process.returncode != 0, "Expected rejection")
                expect(reason.lower() in process.stderr.lower(), "Useful rejection reason: " + reason)
                if preserve:
                    expect(all(p.read_text(encoding="utf-8") == "earlier valid sentinel" for p in output.iterdir()), "Earlier reports unchanged")
                else:
                    expect(not output.exists(), "No output directory on validation failure")
            else:
                expect(process.returncode == 0, "Producer exit zero")
                report = json.loads((output / "route-coverage.json").read_text(encoding="utf-8"))
                html = (output / "route-coverage.html").read_text(encoding="utf-8")
                expect(report["input_sha256"] == hashlib.sha256(input_path.read_bytes()).hexdigest(), "Exact input-byte hash")
                if check:
                    check(report, html, expect)
            result["passed"] = True
        except (AssertionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            result["failure"] = str(exc)
            if isinstance(exc, subprocess.TimeoutExpired):
                result.update(stdout=str(exc.stdout), stderr=str(exc.stderr), exit_code=None)
        write(folder / "result.json", result)
        results.append(result)
        print(("PASS: " if result["passed"] else "FAIL: ") + label)

    def valid(report, html, expect):
        expect(hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == HASH, "Prepared fixture SHA256 after CRLF normalization")
        expect(tuple(report["totals"][key] for key in KEYS) == (10, 26, 13, 13, 0, 0), "Independent total anchors")
        expect(len(report["routes"]) == 3, "Three observed routes")
        for row in report["routes"]:
            published, counts = ANCHORS[row["line_ref"]]
            expect(row["published_name"] == published and tuple(row[key] for key in KEYS) == counts, "Independent anchors " + published)
            expect(row["line_ref"] in html and published in html, "HTML route identity " + published)
            expect("".join("<td>" + str(value) + "</td>" for value in counts) in html, "HTML count anchors " + published)
        expect("not proof of poor service" in report["routes"][-1]["actual_data_availability"], "660 availability separate from performance")
        source = report["source"]
        expect(source["response_sha256"] == ORIGINAL and report["input_sha256"] != ORIGINAL, "Distinct original-response hash")
        expect(source["source_url"] == "https://api.entur.io/realtime/v1/rest/et?datasetId=INN&maxSize=100", "Source URL")
        expect(source["retrieved_at_utc"] == "2026-10-21T14:12:00.852467+00:00" and source["server_date"] == "Wed, 21 Oct 2026 14:11:49 GMT" and report["service_dates"] == ["2026-10-21"], "Source and service dates")
        expect(source["attribution"] == "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS." and source["licence_url"] == "https://data.norge.no/nlod/no/2.0", "Attribution and licence")
        expect(source["modified"] is True and source["selection"]["complete_hamar_coverage"] is False and source["selection"]["original_page_journey_count"] == 100, "Modified partial first-page selection")
        expect(source["selection"]["quays"] == QUAYS, "Exact six-quay mapping")
        for key, value in QUAYS.items():
            expect(key in html and value in html, "HTML quay " + key)
        limits = " ".join(report["interpretation_limits"])
        for phrase in ("100 INN journeys", "six quays", "three selected stops", "no complete city/day", "not absence", "Predictions are separate", "missing data is unknown", "not independently verified physical events", "not passenger counts", "No recurring patterns", "causes", "municipal benefit"):
            expect(phrase in limits and phrase in html, "Interpretation limit: " + phrase)
        expect("Saved 21 October snapshot at three Hamar stops" in html and escape(source["source_url"], quote=True) in html, "HTML title and escaped provenance")

    case("valid-fixture", check=valid)

    def fixture_copy(report, html, expect):
        expect(report["input_sha256"] == hashlib.sha256(input_path.read_bytes()).hexdigest(), "Exact copied-fixture byte hash")

    for label, line_ending in (("fixture-lf-copy", b"\n"), ("fixture-crlf-copy", b"\r\n")):
        input_path = run / label / "synthetic.json"
        case(label, check=fixture_copy, line_ending=line_ending)
    case("duplicate-journey", lambda d: d["journeys"].append(copy.deepcopy(d["journeys"][0])), "Duplicate journey")
    case("duplicate-call", lambda d: d["journeys"][0]["RecordedCalls"]["RecordedCall"].append(copy.deepcopy(next(calls(d)))), "Duplicate call")
    case("malformed-actual", lambda d: next(calls(d)).update(ActualDepartureTime="bad"), "Malformed timestamp")

    def remove_actuals(d):
        for call in calls(d):
            call.pop("ActualArrivalTime", None)
            call.pop("ActualDepartureTime", None)

    def no_actuals(report, html, expect):
        expect(tuple(report["totals"][key] for key in KEYS) == (10, 26, 0, 13, 13, 0), "RecordedCalls do not establish actuals: 0 actual, 13 predictions, 13 unknown")

    case("no-actuals", remove_actuals, check=no_actuals)
    case("unknown-quay", lambda d: next(calls(d))["StopPointRef"].update(value="NSR:Quay:999"), "quay")
    case("mismatched-name", lambda d: next(calls(d))["StopPointName"][0].update(value="Wrong"), "quay")
    case("conflicting-line-name", lambda d: d["journeys"][1]["PublishedLineName"][0].update(value="Wrong"), "Conflicting published name")
    case("missing-input", missing=True, reason="No such file")
    case("invalid-preserves-reports", lambda d: next(calls(d)).update(ActualDepartureTime="bad"), "Malformed timestamp", preserve=True)
    case("timezone-required", lambda d: next(calls(d)).update(ExpectedArrivalTime="2026-10-21T12:00:00"), "Malformed timestamp")
    case("cancelled-invalid-time", lambda d: next(calls(d)).update(Cancellation=True, ActualDepartureTime="bad"), "Malformed timestamp")
    case("strict-boolean", lambda d: next(calls(d)).update(Cancellation="false"), "boolean")
    case("unexpected-identifier", lambda d: d["journeys"][0].update(VehicleRef={"value": "synthetic"}), "Unexpected fields")
    case("invalid-service-date", lambda d: d["journeys"][0]["FramedVehicleJourneyRef"]["DataFrameRef"].update(value="2026-02-30"), "day is out of range")

    def cancellation(report, html, expect):
        expect(tuple(report["totals"][key] for key in KEYS) == (10, 26, 12, 13, 0, 1), "Cancellation precedes actual classification")

    case("cancellation-precedence", lambda d: next(calls(d)).update(Cancellation=True), check=cancellation)

    def escaped(report, html, expect):
        expect("&lt;script&gt;synthetic&lt;/script&gt;" in html and "<script>synthetic</script>" not in html, "Source text HTML escaped")

    case("html-escaping", lambda d: d.update(attribution="<script>synthetic</script>"), check=escaped)
    case("strict-order", lambda d: next(calls(d)).update(Order=True), "integer")
    case("bad-source-hash", lambda d: d.update(response_sha256="invalid"), "hash")
    case("invalid-quay-metadata", lambda d: d["selection"]["quays"].update({"NSR:Quay:17900": "Wrong"}), "quay mapping")

    def other_date(d):
        for journey in d["journeys"]:
            journey["FramedVehicleJourneyRef"]["DataFrameRef"]["value"] = "2026-10-22"

    def date_check(report, html, expect):
        expect(report["service_dates"] == ["2026-10-22"], "Valid service dates parsed without hard-coded analysis date; synthetic only")

    case("other-valid-service-date", other_date, check=date_check)

    def other_line(d):
        for journey in d["journeys"]:
            if journey["LineRef"]["value"] == "INN:Line:22":
                journey["LineRef"]["value"] = "INN:Line:999"
                journey["PublishedLineName"][0]["value"] = "Synthetic999"

    def line_check(report, html, expect):
        expect(any(row["line_ref"] == "INN:Line:999" and row["published_name"] == "Synthetic999" and row["actual"] == 3 for row in report["routes"]), "Other well-formed lines accepted; synthetic only")

    case("other-valid-line", other_line, check=line_check)
    passed = sum(item["passed"] for item in results)
    write(run / "summary.json", dict(passed=passed, total=len(results), model_requests=0, live_requests=0, cases=results))
    print(f"{'PASS' if passed == len(results) else 'FAIL'}: {passed}/{len(results)} offline cases; zero model requests")
    print(run / "summary.json")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
