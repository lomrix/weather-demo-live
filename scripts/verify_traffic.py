"""Repeatable saved-data checks; no network, model, or third-party dependencies."""

import copy
import hashlib
from html import escape
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ROAD = ROOT / "fixtures/hamar-traffic-2026-10-20.json"
BUS = ROOT / "fixtures/hamar-b21-timing-2026-10-21.json"
LABEL = "OFFLINE REPLAY - synthetic decision; not real AI execution"
FOLLOWUP = "Collect road and bus samples for matching dates/periods before comparing them."
ATTRIBUTION = "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS."
# Reviewed expectations, intentionally independent of controller imports.
LIMITATIONS = [
    "A small saved snapshot, not representative daily or regional coverage or recurring delay rates.",
    "Source-reported actuals are provider observations, not independently verified physical events or evidence of a legal service breach.",
    "Predictions are separate from actual comparisons; missing statistics remain unavailable and cancellations are excluded.",
    "Vehicle passages are not unique travellers or a congestion measure.",
    "Road and bus dates differ; these observations do not establish correlation or a causal link.",
    "Passenger harm, delay causes, intervention success and municipal benefit are not established.",
]
ANCHORS = {
    "road.vang_kirke.total": 19576, "road.vang_kirke.peak": 1834,
    "road.disen_ost.total": 19806, "road.disen_ost.peak": 1831,
    "road.vangsvegen_91.total": 13976, "road.vangsvegen_91.peak": 1149,
    "bus.actual_count": 10, "bus.prediction_only_count": 8,
    "bus.actual_min_seconds": -88, "bus.actual_max_seconds": 289,
}
STAGES = ["inputs_validated", "facts_computed", "context_read_prompt_prepared"]
VALID = {"highlight_ids": ["road.vang_kirke.peak", "bus.actual_max_seconds"],
         "followup_ids": ["collect_same_day_samples"]}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calls(bus):
    for journey in bus["journeys"]:
        for group, singular in (("RecordedCalls", "RecordedCall"), ("EstimatedCalls", "EstimatedCall")):
            for call in journey.get(group, {}).get(singular, []):
                yield journey, group, call


def scalar(value):
    return value["value"] if isinstance(value, dict) else value


def evidence(journey, group, call):
    framed = journey["FramedVehicleJourneyRef"]
    return "/".join(map(str, (scalar(framed["DataFrameRef"]),
                              scalar(framed["DatedVehicleJourneyRef"]),
                              scalar(journey["DirectionRef"]), scalar(call["StopPointRef"]),
                              call["Order"], group)))


def main():
    parent = ROOT / "out/traffic-verification"
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="checks-", dir=parent)).resolve()
    summary = {"platform": platform.platform(), "python": sys.version,
               "evidence_directory": str(directory), "cases": [], "status": "running"}
    print(f"EVIDENCE_DIRECTORY {directory}", flush=True)

    def case(name, mode, decision=None, bus=BUS, road=ROAD, failure=None,
             before_validation=False, boundary=False):
        record = {"case": name, "assertions": [], "status": "running"}
        summary["cases"].append(record)

        def check(condition, description):
            record["assertions"].append({"description": description, "passed": bool(condition)})
            if not condition:
                raise AssertionError(f"{name}: {description}")

        command = [sys.executable, str(ROOT / "harness/traffic_brief.py"),
                   "--mode", mode, "--road-input", str(road), "--bus-input", str(bus)]
        if decision is not None:
            decision_path = directory / f"{name}-decision.json"
            write(decision_path, decision)
            command += ["--decision-file", str(decision_path)]
        record["command"] = command
        try:
            result = subprocess.run(command, cwd=ROOT, shell=False, timeout=30,
                                    capture_output=True, text=True, encoding="utf-8",
                                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
            record.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
            check(result.returncode == (1 if failure else 0), "expected controller exit code")
            paths = [line[len("RUN_DIRECTORY "):] for line in result.stdout.splitlines()
                     if line.startswith("RUN_DIRECTORY ")]
            check(len(paths) == 1, "exactly one printed run directory")
            run = Path(paths[0]).resolve()
            allowed = (ROOT / "out/traffic-brief").resolve()
            check(run.is_relative_to(allowed) and run != allowed, "run directory inside out/traffic-brief")
            check(str(run) not in [c.get("run_directory") for c in summary["cases"][:-1]], "fresh run directory")
            record["run_directory"] = str(run)
            trace = read(run / "trace.json")
            check(trace["run_directory"] == str(run), "trace identifies exact run")
            check(trace["codex_invocation_count"] == 0 and trace["token_usage"] is None,
                  "zero Codex invocations and null token usage")
            finals = [run / name for name in ("briefing.json", "briefing.html", "checked-decision.json")]
            if failure:
                check(trace["status"] == "failed" and failure in (trace["failure_reason"] or ""),
                      "failed trace with expected useful reason")
                check(failure in result.stderr, "expected rejection in stderr")
                check(not any(p.exists() for p in finals), "no final briefing or checked decision")
                check(trace["stages"] == ([] if before_validation else STAGES + ["decision_received"]),
                      "rejection at expected stage")
            else:
                check(trace["failure_reason"] is None and not result.stderr, "no failure or stderr")
                check(trace["status"] == ("prepared" if mode == "prepare" else "checked"), "successful status")
                check(trace["stages"] == STAGES + ([] if mode == "prepare" else
                      ["decision_received", "decision_checked", "briefing_rendered"]), "successful stages")
                check((run / "prompt.txt").is_file(), "prepared prompt exists")
                check(trace["context_sha256"] == digest(ROOT / "context/traffic-brief.md"), "context hash")
                catalogue = read(run / "facts.json")
                expected = dict(ANCHORS)
                if boundary:
                    expected.update({"bus.actual_count": 0, "bus.actual_min_seconds": None,
                                     "bus.actual_max_seconds": None})
                check({k: v["value"] for k, v in catalogue["facts"].items()} == expected,
                      "exact ten reviewed fact IDs and values, predictions separate")
                sources = catalogue["sources"]
                for key, path, date, url in (
                    ("road", road, "2026-10-20", "https://trafikkdata-api.atlas.vegvesen.no"),
                    ("bus", bus, ["2026-10-21"], "https://api.entur.io/realtime/v1/rest/et?datasetId=INN&maxSize=100")):
                    check(sources[key]["date"] == date and sources[key]["url"] == url
                          and sources[key]["input_sha256"] == digest(path), f"{key} dates, URL and input-byte hash")
                raw_bus = read(bus)
                check(sources["bus"]["original_whole_response_sha256"] == raw_bus["response_sha256"]
                      and sources["bus"]["original_whole_response_sha256"] != digest(bus), "original response hash separate")
                check(sources["road"]["provider"] == "Statens vegvesen" and sources["bus"]["provider"] == "Entur AS"
                      and sources["bus"]["attribution"] == ATTRIBUTION and sources["bus"]["filtered"] is True
                      and sources["bus"]["licence_url"] == "https://data.norge.no/nlod/no/2.0", "providers and licence")
                check(catalogue["limitations"] == LIMITATIONS, "six independent mandatory limitations")
                if mode == "prepare":
                    check(not any(p.exists() for p in finals), "prepare has no final files")
                else:
                    check(all(p.is_file() for p in finals), "all checked outputs present")
                    check(read(finals[2]) == decision, "checked selection unchanged")
                    brief = read(finals[0])
                    html = finals[1].read_text(encoding="utf-8")
                    check(brief["execution_label"] == LABEL and trace["execution_label"] == LABEL
                          and LABEL in html and LABEL in result.stdout, "explicit synthetic/offline labels")
                    check(brief["highlights"] == [{"id": k, **catalogue["facts"][k]} for k in decision["highlight_ids"]],
                          "highlights match catalogue including evidence")
                    nodes = read(road)["response"]["data"]["vang_kirke"]["volume"]["byHour"]["edges"]
                    road_ids = [f'{read(road)["points"]["vang_kirke"]}/{n["node"]["from"]}/{n["node"]["to"]}'
                                for n in nodes if n["node"]["total"]["volumeNumbers"]["volume"] == 1834]
                    check(brief["highlights"][0]["evidence_ids"] == road_ids and bool(road_ids), "road peak source-row evidence")
                    # The reviewed maximum belongs to this exact source call, not a generated row.
                    max_id = "2026-10-21/INN:ServiceJourney:53462/Outbound/NSR:Quay:17901/14/RecordedCalls"
                    check(max_id in [evidence(j, g, c) for j, g, c in calls(raw_bus)]
                          and brief["highlights"][1]["evidence_ids"] == [max_id], "bus maximum source-row evidence")
                    check(brief["followups"] == [{"id": "collect_same_day_samples", "text": FOLLOWUP}], "fixed follow-up")
                    check(brief["sources"] == sources and brief["limitations"] == LIMITATIONS, "brief provenance and limitations")
                    for value in [LABEL, FOLLOWUP, ATTRIBUTION, *LIMITATIONS, *road_ids, max_id,
                                  sources["road"]["url"], sources["bus"]["url"], "1834", "289.0",
                                  "Vang kirke peak hour passages", "Max source-reported actual departure minus aimed departure"]:
                        check(escape(value, quote=True) in html, f"HTML content: {value}")
            record["status"] = "passed"
            print(f"PASS {name} (controller exit {result.returncode})", flush=True)
        except Exception as exc:
            record.update(status="failed", error=str(exc))
            if isinstance(exc, subprocess.TimeoutExpired):
                record.update(exit_code=None, stdout=str(exc.stdout or ""), stderr=str(exc.stderr or ""))
            print(f"FAIL {name}: {exc}", flush=True)
        finally:
            write(directory / f"{name}-result.json", record)

    try:
        case("prepare", "prepare")
        case("valid-replay", "replay", VALID)
        case("unknown-highlight", "replay", {**VALID, "highlight_ids": ["road.unknown", "bus.actual_max_seconds"]}, failure="Duplicate or unknown highlight_ids")
        case("duplicate-highlights", "replay", {**VALID, "highlight_ids": VALID["highlight_ids"] + ["road.vang_kirke.peak"]}, failure="Duplicate or unknown highlight_ids")
        case("duplicate-followups", "replay", {**VALID, "followup_ids": VALID["followup_ids"] * 2}, failure="Duplicate or unknown followup_ids")
        malformed = read(BUS)
        next(c for _, _, c in calls(malformed) if "ActualDepartureTime" in c)["ActualDepartureTime"] = "not-a-date"
        bad_path = directory / "malformed-bus.json"
        write(bad_path, malformed)
        case("malformed-time", "prepare", bus=bad_path, failure="Malformed timestamp", before_validation=True)
        case("missing-input", "prepare", bus=directory / "missing.json", failure="No such file or directory", before_validation=True)
        missing_actuals = copy.deepcopy(read(BUS))
        for _, _, call in calls(missing_actuals):
            for field in ("ActualArrivalTime", "ActualDepartureTime"):
                call.pop(field, None)
        boundary_path = directory / "no-actuals-bus.json"
        write(boundary_path, missing_actuals)
        case("no-actuals-prepare", "prepare", bus=boundary_path, boundary=True)
        case("unavailable-actual", "replay", VALID, bus=boundary_path, failure="Unavailable statistic selected")
        summary["status"] = "passed" if all(c["status"] == "passed" for c in summary["cases"]) else "failed"
    except Exception as exc:
        summary.update(status="failed", error=str(exc))
        print(f"FAIL verification setup: {exc}")
    finally:
        write(directory / "summary.json", summary)
    passed = summary["status"] == "passed" and len(summary["cases"]) == 9
    print(f"{'PASS' if passed else 'FAIL'}: {sum(c['status'] == 'passed' for c in summary['cases'])}/9 offline cases; zero model requests")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
