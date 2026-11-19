"""Compare sentence-bound extraction with the preserved first diagnostic run.

Default offline baseline mode makes no model calls. This is a development-set
comparison, not held-out evidence. Raw and quote-checked scores stay separate.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from time import perf_counter
from urllib.request import urlopen

from .notice_evaluation import load_cases, keyword_baseline, score_draft, sha256
from .notice_evidence import VERSION, NUM_PREDICT, TIMEOUT_SECONDS, build_evidence_prompt, extract_evidence_notice, check_evidence, flatten_response, source_candidates

PREVIOUS = "fixtures/notice-evaluation/runs/2026-11-19/results.json"
EXPECTED_STATUS = {
    "hamar-koigen-footpath": "closed",
    "synthetic-explicit-footpath-dates": "closed",
    "synthetic-footpath-open": "open",
    "synthetic-source-instruction": "closed",
}


def measure(cases, models, max_requests=8, opener=urlopen, progress=None):
    if (not cases or not models or len(set(models)) != len(models)
            or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,100}", model) for model in models)):
        raise ValueError("Choose nonempty cases and unique explicit local model names")
    if not 1 <= max_requests <= 8 or len(cases) * len(models) > max_requests:
        raise ValueError("Request ceiling exceeded; no requests made (maximum eight)")
    rows = []
    for case in cases:
        for model in models:
            if progress:
                progress(f"{case['id']}: {model}")
            row = {"case_id": case["id"], "kind": case["kind"], "method": model,
                   "status": "failed", "requests_made": 1, "raw_score": None, "checked_score": None,
                   "expected_access_status": EXPECTED_STATUS[case["id"]]}
            started = perf_counter()
            try:
                result = extract_evidence_notice(case["input"], opener=opener, model=model)
                row.update(result)
                selected = next((item for item in result["raw_draft"]["consequences"]
                                 if item["sentence_id"] == result["raw_draft"]["selected_sentence_id"]), None)
                row["raw_access_status"] = selected["access_status"] if selected else "unknown"
                if selected:
                    row["raw_score"] = score_draft(result["model_draft"], case)
                    checked = {**result["checked"]["fields"],
                               "supporting_sentence_ids": [selected["sentence_id"]]}
                    row["checked_score"] = score_draft(checked, case)
                    row["status"] = "ok"
                else:
                    row["status"] = "abstained"
            except (RuntimeError, ValueError) as exc:
                row["error"] = str(exc)
                row["requests_made"] = getattr(exc, "requests_made", 1)
                if hasattr(exc, "raw_model_reply"):
                    row["raw_model_reply"] = exc.raw_model_reply
            row["elapsed_seconds"] = round(perf_counter() - started, 3)
            rows.append(row)
    return rows


def report_markdown(report, previous):
    rows = report["results"]
    old = {(row["case_id"], row["method"]): row for row in previous["results"]}
    lines = ["# Evidence-linked extraction: development comparison", "",
             f"Generated: {report['generated_at']}. Version: {VERSION}. "
             f"New local model requests: {report['requests_made']}. "
             f"Archived model requests rechecked: {report.get('replayed_model_requests', 0)}.", "",
             "The source texts, focus and prepared references are unchanged. The revised prompt and "
             f"response schema changed together. The output budget changed from 400 to {NUM_PREDICT} tokens. "
             "Python retrieves a narrowed source set and constrains sentence IDs, modes and statuses. "
             "This measures the combined retrieval/rules/schema/model revision, not the "
             "isolated effect of one change. All cases are now development examples.", "",
             "Raw extraction and Python's quote-checked output are scored separately. Withholding an "
             "unsupported date is a guardrail result, not evidence that the model extracted it correctly. "
             "Exact-match scores can penalise valid alternative quotes. Checked unknown dates may match "
             "a null reference even when no other field survives review; inspect coverage below.", "",
             "| Model | Evidence | Answered / attempted | Before raw fields | Revised raw fields | Quote-checked fields | Unexpected dates / valid raw answers: before → revised |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    groups = sorted({(row["method"], row["kind"]) for row in rows})
    for model, kind in groups:
        selected = [row for row in rows if row["method"] == model and row["kind"] == kind]
        before = [old[(row["case_id"], model)] for row in selected if (row["case_id"], model) in old]
        count = len(selected) * 4
        matched = lambda group, key: sum(row.get(key, {}).get("matched_fields", 0) if row.get(key) else 0 for row in group)
        dates = lambda group, key: sum(bool(row.get(key, {}).get("unexpected_date_claim")) if row.get(key) else False for row in group)
        valid = sum(row.get('raw_score') is not None for row in selected)
        old_valid = sum(row.get('score') is not None for row in before)
        lines.append(f"| {model} | {kind} | {valid}/{len(selected)} | {matched(before, 'score')}/{len(before) * 4} | "
                     f"{matched(selected, 'raw_score')}/{count} | {matched(selected, 'checked_score')}/{count} | "
                     f"{dates(before, 'score')}/{old_valid} → {dates(selected, 'raw_score')}/{valid} |")
    if report.get("focused_baseline"):
        lines += ["", "## Non-AI reader with the same source retrieval", "",
                  "This stronger comparator uses the identical candidate filter followed by the fixed "
                  "keyword reader. Retrieval improvements must not be attributed to the model alone.", ""]
        for row in report["focused_baseline"]:
            score = row.get("score")
            lines.append(f"- {row['case_id']}: {score['matched_fields'] if score else 0}/4 exact fields.")
    lines += ["", "## Individual results", ""]
    for row in rows:
        lines += [f"### {row['case_id']} — {row['method']}", "", f"Status: {row['status']}; {row['elapsed_seconds']} s."]
        if row.get("checked"):
            lines += [f"Access status: raw **{row['raw_access_status']}**; quote-checked "
                      f"**{row['checked']['access_status']}**; reference **{row['expected_access_status']}**.",
                      f"Review issues: {' '.join(row['checked']['issues']) or 'No literal inconsistency detected; human review remains required.'}",
                      f"Retained non-date fields: {sum(value not in (None, []) for key,value in row['checked']['fields'].items() if key != 'stated_dates')}/3.",
                      "", "Raw selected fields:", "```json", json.dumps(row["model_draft"], ensure_ascii=False, indent=2), "```", "",
                      "Quote-checked fields:", "```json", json.dumps(row["checked"]["fields"], ensure_ascii=False, indent=2), "```", ""]
        if row.get("error"):
            lines += [f"Failure: {row['error']}", ""]
    lines += ["## Limits", "",
              "- The real Koigen notice is known, and the other three texts are synthetic; report them separately.",
              "- References and expected status labels are author-prepared; independent teammate review remains pending.",
              "- Same-sentence quotes can still describe the wrong subject; these checks do not prove semantic correctness.",
              "- The mode/status/instruction patterns are narrow Norwegian/English checks, not a general verifier or injection defence.",
              "- Dates in separate sentences are withheld, even when a person could link them correctly.",
              "- Lexical retrieval can miss a consequence or select the wrong location. Mode/status constraints come from Python, so correct constrained answers are not independent model inferences.",
              "- One selected consequence is reviewed at a time; recall of every consequence is not measured.",
              "- Human confirmation, source verification and map review remain required; no model answer establishes geometry or physical access.",
              "- These runs do not establish repeatability, time savings, user demand or general superiority over a non-AI reader.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["baseline", "live"], default="baseline")
    parser.add_argument("--models", nargs="+", default=[])
    parser.add_argument("--max-requests", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", type=Path, help="Recheck an archived revised run offline; makes zero model calls")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.output.exists():
            raise ValueError("Choose a new output directory; existing evidence is preserved")
        cases, manifest_hash = load_cases(root)
        previous_raw = (root / PREVIOUS).read_bytes()
        previous = json.loads(previous_raw)
        before_cases = {case["id"]: case for case in previous["cases"]}
        for case in cases:
            if any(case[key] != before_cases[case["id"]][key] for key in ("input", "reference", "prompt_sha256")):
                raise ValueError("Source/focus/reference/original prompt changed; comparison refused")
        replayed_requests = 0
        if args.replay:
            if args.mode == "live" or args.models:
                raise ValueError("Replay is offline; do not combine it with live mode or model names")
            archived = json.loads(args.replay.read_text(encoding="utf-8"))
            archived_cases = {case["id"]: case for case in archived["cases"]}
            for case in cases:
                if any(case[key] != archived_cases[case["id"]][key] for key in ("input", "reference")):
                    raise ValueError("Replay source/focus/reference changed")
                if sha256(build_evidence_prompt(case["input"]).encode("utf-8")) != archived_cases[case["id"]]["revised_prompt_sha256"]:
                    raise ValueError("Replay prompt changed; preserve the original run")
            rows = archived["results"]
            case_map = {case["id"]: case for case in cases}
            for row in rows:
                replayed_requests += row["requests_made"]
                row["requests_made"] = 0
                if "raw_draft" in row:
                    case = case_map[row["case_id"]]
                    row["previous_checks"] = row["checked"]
                    row["checked"] = check_evidence(row["raw_draft"], case["input"])
                    if row["raw_score"]:
                        checked = {**row["checked"]["fields"], "supporting_sentence_ids": row["model_draft"]["supporting_sentence_ids"]}
                        row["checked_score"] = score_draft(checked, case)
        else:
            rows = measure(cases, args.models, args.max_requests,
                           progress=lambda message: print(message, flush=True)) if args.mode == "live" else []
        focused_baseline = []
        for case in cases:
            candidates = source_candidates(case["input"])
            draft = keyword_baseline({"sentences": [candidates[0]["text"]]}) if candidates else None
            if draft:
                draft["supporting_sentence_ids"] = [candidates[0]["sentence_id"]]
            focused_baseline.append({"case_id": case["id"], "draft": draft, "score": score_draft(draft, case) if draft else None})
        report = {"version": VERSION, "mode": args.mode,
                  "generated_at": datetime.now(timezone.utc).isoformat(), "requests_made": sum(row["requests_made"] for row in rows),
                  "replayed_model_requests": replayed_requests,
                  "replay_file": str(args.replay) if args.replay else None,
                  "replay_sha256": sha256(args.replay.read_bytes()) if args.replay else None,
                  "previous_run_file": PREVIOUS, "previous_run_sha256": sha256(previous_raw),
                  "manifest_sha256": manifest_hash,
                  "extractor_sha256": sha256((root / "harness/notice_evidence.py").read_bytes()),
                  "evaluator_sha256": sha256(Path(__file__).read_bytes()),
                  "cases": [{**case, "revised_prompt_sha256": sha256(build_evidence_prompt(case["input"]).encode("utf-8"))} for case in cases],
                  "baseline": [{"case_id": case["id"], "draft": keyword_baseline(case["input"]),
                                "score": score_draft(keyword_baseline(case["input"]), case)} for case in cases],
                  "focused_baseline": focused_baseline, "results": rows,
                  "request_limits": {"max_requests": args.max_requests, "timeout_seconds": TIMEOUT_SECONDS,
                                     "max_response_bytes": 16384, "num_predict": NUM_PREDICT, "retries": 0}}
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.output / "report.md").write_text(report_markdown(report, previous), encoding="utf-8")
        print(f"Saved {args.output / 'report.md'}")
        return 1 if any(row["status"] != "ok" for row in rows) else 0
    except (OSError, ValueError) as exc:
        print(f"Comparison stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
