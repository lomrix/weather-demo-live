"""Bounded saved-data briefing: explicit prepare, synthetic replay, or Codex mode."""

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
from traffic_report import analyse as analyse_road
from bus_timing_report import analyse as analyse_bus

ROOT = Path(__file__).resolve().parents[1]
FOLLOWUPS = {
    "collect_same_day_samples": "Collect road and bus samples for matching dates/periods before comparing them.",
    "repeat_bus_observations": "Obtain bounded observations over comparable days before claiming recurring patterns.",
    "check_early_departure_records": "Confirm the meaning of source-reported early departures before interpreting service performance.",
}
LIMITATIONS = [
    "A small saved snapshot, not representative daily or regional coverage or recurring delay rates.",
    "Source-reported actuals are provider observations, not independently verified physical events or evidence of a legal service breach.",
    "Predictions are separate from actual comparisons; missing statistics remain unavailable and cancellations are excluded.",
    "Vehicle passages are not unique travellers or a congestion measure.",
    "Road and bus dates differ; these observations do not establish correlation or a causal link.",
    "Passenger harm, delay causes, intervention success and municipal benefit are not established.",
]
ACTUAL_IDS = {"bus.actual_count", "bus.actual_min_seconds", "bus.actual_max_seconds"}
PERMISSION_CONFIG = 'permissions.traffic-brief={filesystem={":minimal"="read",":workspace_roots"={"."="read",".env"="deny",".env.local"="deny"}},network={enabled=false}}'
MAX_EVENTS = 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_json(path, limit=None):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1) if limit else stream.read()
    require(limit is None or len(raw) <= limit, f"JSON exceeds {limit} bytes")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs), hashlib.sha256(raw).hexdigest()


def catalogue(road, bus, hashes):
    sources = {
        "road": {"date": road["date"], "url": road["provenance"]["source"],
                 "retrieved_at": road["provenance"]["retrieved_at_utc"], "input_sha256": hashes[0],
                 "provider": "Statens vegvesen"},
        "bus": {"date": sorted({call["data_frame_ref"] for call in bus["calls"]}),
                "url": bus["provenance"]["source_url"],
                "retrieved_at": bus["provenance"]["retrieved_at_utc"], "input_sha256": hashes[1],
                "provider": "Entur AS", "attribution": bus["provenance"]["attribution"],
                "licence_url": bus["provenance"]["licence_url"], "filtered": True,
                "original_whole_response_sha256": bus["provenance"]["response_sha256"]},
    }
    facts = {}
    def add(identifier, value, unit, source, label, evidence):
        facts[identifier] = {"value": value, "unit": unit, "source_id": source,
                             "date": sources[source]["date"], "source_url": sources[source]["url"],
                             "label": label, "evidence_ids": evidence}
    for counter in road["counters"]:
        evidence = [f'{counter["counter_id"]}/{hour["from"]}/{hour["to"]}' for hour in counter["hourly"]]
        add(f'road.{counter["source_key"]}.total', counter["daily_vehicle_passages"],
            "vehicle passages", "road", counter["name"] + " daily passages", evidence)
        peak_evidence = [f'{counter["counter_id"]}/{p["from"]}/{p["to"]}' for p in counter["peak_intervals"]]
        add(f'road.{counter["source_key"]}.peak', counter["peak_vehicle_passages"],
            "vehicle passages in the peak hour", "road", counter["name"] + " peak hour passages", peak_evidence)
    actual = [c for c in bus["calls"] if c["category"] == "actual"]
    predicted = [c for c in bus["calls"] if c["category"] == "prediction_only"]
    def ids(calls):
        return [f'{c["data_frame_ref"]}/{c["journey_id"]}/{c["direction"]}/{c["stop_id"]}/{c["order"]}/{c["source_call_group"]}' for c in calls]
    add("bus.actual_count", len(actual), "stop-call comparisons", "bus", "Source-reported actual departure comparisons", ids(actual))
    add("bus.prediction_only_count", len(predicted), "stop-call predictions", "bus", "Prediction-only departure comparisons", ids(predicted))
    for kind in ("min", "max"):
        value = bus["summary"]["actual_difference_seconds"][kind]
        add(f"bus.actual_{kind}_seconds", value, "signed seconds", "bus",
            f"{kind.title()} source-reported actual departure minus aimed departure",
            ids([c for c in actual if c["departure_difference_seconds"] == value]))
    return {"sources": sources, "facts": facts, "limitations": LIMITATIONS}


def checked_decision(decision, facts):
    require(type(decision) is dict and set(decision) == {"highlight_ids", "followup_ids"}, "Decision must have exactly highlight_ids and followup_ids")
    for key, low, high, allowed in (("highlight_ids", 2, 4, facts), ("followup_ids", 1, 2, FOLLOWUPS)):
        values = decision[key]
        require(type(values) is list and low <= len(values) <= high and all(type(v) is str for v in values), f"Invalid {key} type or count")
        require(len(set(values)) == len(values) and all(v in allowed for v in values), f"Duplicate or unknown {key}")
    selected = decision["highlight_ids"]
    require(any(v.startswith("road.") for v in selected) and bool(ACTUAL_IDS.intersection(selected)), "Highlights require road and bus actual evidence")
    require(all(facts[v]["value"] is not None for v in selected), "Unavailable statistic selected")
    return decision


def stop_tree(process):
    if os.name == "nt":
        # /T targets only this child's process tree, never a name-wide process kill.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def run_codex(executable, prompt, directory, trace):
    draft = directory / "draft-decision.json"
    command = [executable, "exec", "--json", "--ephemeral", "--strict-config",
               "--output-schema", str(ROOT / "context/traffic-brief.schema.json"),
               "-o", str(draft), "-C", str(ROOT), "-c", PERMISSION_CONFIG,
               "-c", 'default_permissions="traffic-brief"', "-"]
    trace["command"] = command
    trace["codex_invocation_count"] = 1
    write_json(directory / "trace.json", trace)
    started = time.monotonic()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=False, start_new_session=os.name != "nt",
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    overflow = threading.Event()
    failures = []
    def capture(stream, path):
        try:
            size = 0
            with path.open("wb") as output:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    remaining = MAX_EVENTS - size
                    output.write(chunk[:max(0, remaining)])
                    size += len(chunk)
                    if size > MAX_EVENTS:
                        overflow.set()
                        break
        except Exception as exc:
            failures.append(str(exc))
            overflow.set()
    readers = [threading.Thread(target=capture, args=(stream, directory / name), daemon=True)
               for stream, name in ((process.stdout, "codex-events.jsonl"), (process.stderr, "codex-stderr.txt"))]
    for reader in readers:
        reader.start()
    def feed():
        try:
            process.stdin.write(prompt.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    try:
        while process.poll() is None or any(reader.is_alive() for reader in readers):
            require(time.monotonic() - started < 120, "Codex whole-process timeout (120 seconds)")
            require(not overflow.is_set(), "Codex output capture size limit exceeded or capture failed")
            require(not draft.exists() or draft.stat().st_size <= 4096, "Draft decision exceeds 4096 bytes")
            time.sleep(.02)
        require(not overflow.is_set() and not failures, "Codex capture failed or exceeded size limit")
        trace["process_exit_code"] = process.returncode
        require(process.returncode == 0, f"Codex process exited {process.returncode}")
        completed = False
        for line in (directory / "codex-events.jsonl").read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            kind = event.get("type")
            item = event.get("item", {})
            require(item.get("type") not in {"command_execution", "file_change", "mcp_tool_call", "web_search"}, "Forbidden tool event in Codex run")
            require(kind not in {"error", "turn.failed"}, "Codex reported failed/error event")
            if kind == "turn.completed":
                completed = True
                trace["token_usage"] = event.get("usage")
        require(completed, "No completed Codex turn")
        return load_json(draft, 4096)[0]
    finally:
        if process.poll() is None or any(reader.is_alive() for reader in readers):
            stop_tree(process)
        for reader in readers:
            reader.join(timeout=1)


def render(brief):
    esc = lambda value: escape(str(value), quote=True)
    items = []
    for fact in brief["highlights"]:
        evidence = "; ".join(fact["evidence_ids"])
        items.append(f'<li><strong>{esc(fact["label"])}: {esc(fact["value"])} {esc(fact["unit"])}</strong> — {esc(fact["date"])}. <a href="{esc(fact["source_url"])}">{esc(fact["source_id"])}</a><details><summary>Evidence identifiers</summary>{esc(evidence)}</details></li>')
    sources = []
    for key, source in brief["sources"].items():
        sources.append(f'<li>{esc(source["provider"])}: <a href="{esc(source["url"])}">{esc(key)}</a>; source date {esc(source["date"])}; input-file SHA256 {esc(source["input_sha256"])}. {esc(source.get("attribution", ""))}</li>')
    bus = brief["sources"]["bus"]
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Checked traffic briefing</title>
<style>body{{font:17px system-ui;max-width:960px;margin:2rem auto;padding:1rem;line-height:1.5}}li{{margin:.7rem 0}}details{{overflow-wrap:anywhere}}</style>
<h1>Checked draft for human review</h1><p>{esc(brief["execution_label"])}</p><h2>Selected evidence</h2><ul>{''.join(items)}</ul>
<h2>Follow-up questions</h2><ul>{''.join('<li>'+esc(q['text'])+'</li>' for q in brief['followups'])}</ul>
<h2>Mandatory limitations</h2><ul>{''.join('<li>'+esc(v)+'</li>' for v in brief['limitations'])}</ul>
<h2>Sources and input hashes</h2><ul>{''.join(sources)}</ul><p>Bus data was filtered. <a href="{esc(bus['licence_url'])}">NLOD licence</a>. Original whole-response hash (not fixture bytes): {esc(bus['original_whole_response_sha256'])}.</p></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("prepare", "replay", "codex"))
    parser.add_argument("--decision-file", type=Path)
    parser.add_argument("--road-input", type=Path, default=ROOT / "fixtures/hamar-traffic-2026-10-20.json")
    parser.add_argument("--bus-input", type=Path, default=ROOT / "fixtures/hamar-b21-timing-2026-10-21.json")
    parser.add_argument("--codex-path")
    args = parser.parse_args()
    parent = ROOT / "out/traffic-brief"
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=parent))
    trace = {"mode": args.mode, "run_directory": str(directory), "status": "running", "stages": [],
             "codex_invocation_count": 0, "token_usage": None, "failure_reason": None}
    print(f"RUN_DIRECTORY {directory}", flush=True)
    try:
        require((args.mode == "replay") == (args.decision_file is not None), "Only replay requires --decision-file")
        road_raw, road_hash = load_json(args.road_input)
        bus_raw, bus_hash = load_json(args.bus_input)
        road, bus = analyse_road(road_raw), analyse_bus(bus_raw)
        trace["stages"].append("inputs_validated")
        facts = catalogue(road, bus, (road_hash, bus_hash))
        write_json(directory / "facts.json", facts)
        trace["stages"].append("facts_computed")
        context_path = ROOT / "context/traffic-brief.md"
        context = context_path.read_text(encoding="utf-8")
        trace["context_sha256"] = hashlib.sha256(context_path.read_bytes()).hexdigest()
        # Only fixed instruction text and computed numeric facts enter the prompt, never raw source strings.
        prompt_facts = {key: {"value": value["value"], "unit": value["unit"]} for key, value in facts["facts"].items()}
        prompt = context + "\nVerified source dates: road 2026-10-20; bus 2026-10-21.\nVerified fact catalogue:\n" + json.dumps(prompt_facts, ensure_ascii=False) + "\nPermitted follow-ups:\n" + json.dumps(FOLLOWUPS) + "\nReturn IDs only.\n"
        require(len(prompt) <= 12000, "Prompt exceeds 12000 characters")
        (directory / "prompt.txt").write_text(prompt, encoding="utf-8")
        trace["prompt_characters"] = len(prompt)
        trace["stages"].append("context_read_prompt_prepared")
        if args.mode == "prepare":
            trace["status"] = "prepared"
            print("PREPARED; zero Codex invocations; no final briefing")
        else:
            if args.mode == "replay":
                trace["execution_label"] = "OFFLINE REPLAY - synthetic decision; not real AI execution"
                decision = load_json(args.decision_file, 4096)[0]
            else:
                trace["execution_label"] = "Real Codex selection - checked draft for human review"
                known = Path.home() / "AppData/Local/Programs/OpenAI/Codex/bin/codex.exe"
                executable = args.codex_path or shutil.which("codex.exe") or (str(known) if known.is_file() else None)
                require(executable is not None, "Installed codex.exe not found")
                decision = run_codex(executable, prompt, directory, trace)
            trace["stages"].append("decision_received")
            checked_decision(decision, facts["facts"])
            trace["stages"].append("decision_checked")
            write_json(directory / "checked-decision.json", decision)
            brief = {"status": "checked draft for human review", "execution_label": trace["execution_label"],
                     "highlights": [{"id": key, **facts["facts"][key]} for key in decision["highlight_ids"]],
                     "followups": [{"id": key, "text": FOLLOWUPS[key]} for key in decision["followup_ids"]],
                     "sources": facts["sources"], "limitations": LIMITATIONS}
            html = render(brief)
            write_json(directory / "briefing.json", brief)
            (directory / "briefing.html").write_text(html, encoding="utf-8")
            trace["stages"].append("briefing_rendered")
            trace["status"] = "checked"
            print(f'{trace["execution_label"]}; generated {directory / "briefing.json"} and {directory / "briefing.html"}')
    except (Exception, KeyboardInterrupt) as exc:
        trace["status"] = "failed"
        trace["failure_reason"] = str(exc) or type(exc).__name__
        print(f'FAILED: {trace["failure_reason"]}; no successful current briefing; older runs may be stale.', file=sys.stderr)
        return 1
    finally:
        write_json(directory / "trace.json", trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
