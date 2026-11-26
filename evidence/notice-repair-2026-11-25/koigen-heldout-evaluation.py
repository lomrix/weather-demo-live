"""Run the existing notice extractor and scoring after human reference approval."""
import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

LOCAL = Path(__file__).resolve().parent
REPO = Path.cwd()
sys.path.insert(0, str(REPO))
from harness.notice_draft import article_sentences
from harness.notice_evaluation import FIELDS, keyword_baseline, normal, score_draft, sha256, validate_draft
from harness.notice_evidence import (
    MAX_RESPONSE_BYTES, NUM_PREDICT, STATUSES, TIMEOUT_SECONDS, VERSION,
    build_evidence_prompt, extract_evidence_notice, response_schema, source_candidates,
)
from harness.workspace_service import Recorder

MODELS = ("qwen2.5:3b", "qwen3.5:9b")
INPUTS = LOCAL / "koigen-heldout-inputs.json"

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def baseline(case):
    notice = case["input"]
    started = perf_counter()
    draft = keyword_baseline(notice)
    return {
        "method": "keyword_baseline", "status": "ok" if draft else "abstained",
        "raw_draft": draft, "score": score_draft(draft, case) if draft else unavailable_score(case),
        "access_status": "not emitted by baseline", "program_seconds": perf_counter() - started,
    }

def unavailable_score(case):
    return {
        "field_matches": dict.fromkeys(FIELDS, False),
        "matched_fields": 0, "total_fields": len(FIELDS),
        "missing_required_fields": [
            field for field in FIELDS if case["reference"][field] not in (None, [])
        ],
    }

def model_run(case, model, output, digest, disable_reasoning=False):
    def open_request(request, *args, **kwargs):
        if disable_reasoning:
            body = json.loads(request.data)
            body["think"] = False
            request = Request(request.full_url, data=json.dumps(body).encode("utf-8"),
                              headers=dict(request.header_items()), method=request.get_method())
        return urlopen(request, *args, **kwargs)

    recorder = Recorder(open_request)
    started = perf_counter()
    row = {"method": model, "digest": digest, "request_options": {"think": False} if disable_reasoning else {}}
    try:
        result = extract_evidence_notice(case["input"], opener=recorder, model=model)
        checked = result["checked"]
        selected = result["raw_draft"]["selected_sentence_id"]
        raw_status = result["raw_draft"]["consequences"][0]["access_status"]
        expected = case["access_status"]
        row.update(result, status="ok", raw_access_status=raw_status,
                   raw_status_match=raw_status == expected,
                   checked_status_match=checked["access_status"] == expected,
                   raw_score=score_draft(result["model_draft"], case),
                   checked_score=score_draft({**checked["fields"], "supporting_sentence_ids": [selected]}, case))
    except (RuntimeError, ValueError) as error:
        row.update(status="failed" if recorder.calls else "retrieval_abstained",
                   error=str(error), raw_score=unavailable_score(case),
                   checked_score=unavailable_score(case))
        if hasattr(error, "raw_model_reply"):
            row["raw_model_reply"] = error.raw_model_reply
    row["pipeline_seconds"] = round(perf_counter() - started, 3)
    row["requests_made"] = recorder.calls
    if recorder.raw is not None:
        name = f"{case['id']}-{model.replace(':', '-')}-raw.json"
        (output / name).write_bytes(recorder.raw)
        row["raw_response_file"] = name
        row["raw_response_truncated"] = len(recorder.raw) > MAX_RESPONSE_BYTES
    return row

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="Print numbered source sentences without running any reader")
    parser.add_argument("--labels", type=Path, help="Human-approved JSON keyed by case ID")
    parser.add_argument("--output", type=Path, help="New directory for raw responses and results")
    parser.add_argument("--no-thinking-9b", action="store_true", help="Disable reasoning for Qwen 3.5 9B only")
    args = parser.parse_args()
    cases = load_json(INPUTS)
    for case in cases:
        case["input"] = {"focus": case["focus"], "sentences": article_sentences(case["text"])}
    if args.prepare:
        for case in cases:
            print(case["id"], case["focus"])
            for index, sentence in enumerate(case["input"]["sentences"], 1):
                print(f"{index}. {sentence}")
        return
    if not args.labels or not args.output:
        parser.error("Supply confirmed --labels and a new --output, or use --prepare.")
    labels = load_json(args.labels)
    if set(labels) != {case["id"] for case in cases}:
        parser.error("Supply labels for both and only the two frozen cases.")
    for case in cases:
        label = labels[case["id"]]
        for field in ("reference", "access_status"):
            case[field] = label[field]
        case["human_review_seconds"] = label.get("human_review_seconds")
        notice, reference = case["input"], case["reference"]
        validate_draft(reference, len(notice["sentences"]))
        if case["access_status"] not in STATUSES:
            parser.error(f"Invalid access status for {case['id']}.")
        source = " ".join(notice["sentences"][i - 1] for i in reference["supporting_sentence_ids"])
        if any(reference[field] and normal(reference[field]).casefold() not in normal(source).casefold()
               for field in ("location", "restriction", "stated_dates")):
            parser.error(f"A reference quote for {case['id']} is absent from its cited source.")
        candidates = source_candidates(notice)
        case["prompt"] = build_evidence_prompt(notice)
        case["prompt_sha256"] = sha256(case["prompt"].encode("utf-8"))
        case["schema"] = response_schema(len(notice["sentences"]), candidates)
        case["candidate_sentence_ids"] = [item["sentence_id"] for item in candidates]
    args.output.mkdir(parents=True, exist_ok=False)
    with urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as response:
        models = {item["name"]: item["digest"] for item in json.load(response)["models"]}
    if not set(MODELS) <= models.keys():
        parser.error("The two selected local models must already be installed.")
    results = {
        "python": platform.python_version(), "extractor": VERSION,
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "extractor_sha256": sha256((REPO / "harness/notice_evidence.py").read_bytes()),
        "inputs_sha256": sha256(INPUTS.read_bytes()), "labels_sha256": sha256(args.labels.read_bytes()),
        "maximum_generation_requests": len(cases) * len(MODELS), "retries": 0,
        "num_predict": NUM_PREDICT, "timeout_seconds": TIMEOUT_SECONDS,
        "max_response_bytes": MAX_RESPONSE_BYTES,
        "cases": cases, "results": {},
    }
    for case in cases:
        rows = [baseline(case)]
        for model in MODELS:
            rows.append(model_run(case, model, args.output, models[model], args.no_thinking_9b and model == "qwen3.5:9b"))
        results["results"][case["id"]] = rows
        save_json(args.output / "results.json", results)
    print("Saved", args.output / "results.json")

if __name__ == "__main__":
    main()
