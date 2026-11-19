"""Bounded raw-notice evaluation, independent of reference-based UI correction.

Only the explicit live mode makes model requests. References never enter prompts
or the deterministic baseline. Exact reference mismatch is not proof of a false
claim: another source-supported wording can be valid and needs manual review.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter
from urllib.request import urlopen

from .notice_draft import (
    MODEL, RESPONSE_SCHEMA, TIMEOUT_SECONDS, article_sentences,
    build_prompt, extract_notice, load_notice,
)

FIELDS = ("location", "travel_modes", "restriction", "stated_dates")
CASE_FILE = "fixtures/notice-evaluation/cases.json"
LIMITATIONS = [
    "One known real notice is a development example, not held-out evidence of generalisation.",
    "Synthetic stress cases are reported separately and do not establish real-world accuracy.",
    "References are author-prepared; independent teammate review is pending.",
    "Exact matches measure this extraction contract; a different supported quote may be valid.",
    "Source-quote checks do not prove semantic support, physical access or closure geometry.",
    "Corrected UI fields are excluded: copying the reference cannot count as model accuracy.",
    "A single run per case does not measure repeatability, user time saved or willingness to pay.",
]


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def normal(value):
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return sorted(set(value))
    return value


def validate_draft(draft, sentence_count):
    if not isinstance(draft, dict) or set(draft) != set(RESPONSE_SCHEMA["properties"]):
        raise ValueError("Draft must contain exactly the five extraction fields")
    for key in ("location", "restriction", "stated_dates"):
        if draft[key] is not None and (not isinstance(draft[key], str) or not draft[key].strip()):
            raise ValueError(f"{key} must be nonempty text or null")
    modes = draft["travel_modes"]
    if (not isinstance(modes, list) or any(not isinstance(mode, str) or mode not in
            {"walking", "cycling", "driving", "parking"} for mode in modes)
            or len(set(modes)) != len(modes)):
        raise ValueError("Travel modes must be a unique list of allowed modes")
    ids = draft["supporting_sentence_ids"]
    if (not isinstance(ids, list) or not ids or any(type(i) is not int or
            not 1 <= i <= sentence_count for i in ids) or len(set(ids)) != len(ids)):
        raise ValueError("Citation IDs must be unique integers within the source")


def load_cases(root):
    root = Path(root)
    manifest_bytes = (root / CASE_FILE).read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("version") != 1 or not manifest.get("cases"):
        raise ValueError("Unsupported or empty evaluation manifest")
    cases, seen = [], set()
    for entry in manifest["cases"]:
        if entry["id"] in seen:
            raise ValueError("Duplicate evaluation case ID")
        seen.add(entry["id"])
        if entry["kind"] == "saved_real_notice":
            # Only the fixed existing source is supported; no arbitrary path input.
            if entry["notice_file"] != "fixtures/notices/hamar-koigen-footpath.json":
                raise ValueError("Unreviewed notice fixture path")
            notice = load_notice(root)
            reference = notice["hand_reference"]
            source = {key: notice[key] for key in
                      ("source_url", "retrieved_at", "attribution")}
            source["file"] = entry["notice_file"]
            source["file_sha256"] = sha256((root / entry["notice_file"]).read_bytes())
        elif entry["kind"] == "synthetic":
            notice = {"focus": entry["focus"], "sentences": article_sentences(entry["text"])}
            reference = entry["reference"]
            source = {"file": CASE_FILE, "label": "Invented diagnostic text; no actual works or dates"}
        else:
            raise ValueError("Unknown evaluation case kind")
        validate_draft(reference, len(notice["sentences"]))
        citations = " ".join(notice["sentences"][i - 1] for i in reference["supporting_sentence_ids"])
        if any(reference[key] is not None and normal(reference[key]) not in normal(citations)
               for key in ("location", "restriction", "stated_dates")):
            raise ValueError("Reference quote does not occur in its cited source")
        # Pass only source/focus to extraction: never the reference or focus_quote.
        public_input = {"focus": notice["focus"], "sentences": notice["sentences"]}
        cases.append({"id": entry["id"], "kind": entry["kind"], "challenge": entry["challenge"],
                      "input": public_input, "reference": reference, "source": source,
                      "prompt_sha256": sha256(build_prompt(public_input).encode("utf-8")),
                      "text_sha256": sha256("\n".join(notice["sentences"]).encode("utf-8"))})
    return cases, sha256(manifest_bytes)


def keyword_baseline(notice):
    """First sentence containing gangsti; fixed quote/date rules, no reference."""
    for index, sentence in enumerate(notice["sentences"], 1):
        if "gangsti" not in sentence.lower():
            continue
        date = re.search(r"fra \d{1,2}\. til \d{1,2}\. [a-zæøå]+ \d{4}", sentence)
        clause = re.search(r"\b(?:vil|er)\b.+", sentence)
        location = sentence[:clause.start()].strip() if clause else None
        return {"location": location or None, "travel_modes": ["walking"],
                "restriction": clause.group().rstrip(".") if clause else None,
                "stated_dates": date.group() if date else None,
                "supporting_sentence_ids": [index]}
    return None  # An abstention is recorded as a failed extraction, not excluded.


def score_draft(draft, case):
    reference = case["reference"]
    validate_draft(draft, len(case["input"]["sentences"]))
    fields = {key: normal(draft[key]) == normal(reference[key]) for key in FIELDS}
    expected = set(reference["supporting_sentence_ids"])
    actual = set(draft["supporting_sentence_ids"])
    cited = " ".join(case["input"]["sentences"][i - 1] for i in sorted(actual))
    quotes = {key: draft[key] is None or normal(draft[key]) in normal(cited)
              for key in ("location", "restriction", "stated_dates")}
    return {"field_matches": fields, "matched_fields": sum(fields.values()),
            "total_fields": len(FIELDS), "exact_case": all(fields.values()) and actual == expected,
            "citation_precision": len(actual & expected) / len(actual),
            "citation_recall": len(actual & expected) / len(expected),
            "extra_citation_ids": sorted(actual - expected),
            "missing_citation_ids": sorted(expected - actual),
            "quote_checks": quotes,
            "missing_required_fields": [key for key in FIELDS if reference[key] not in (None, [])
                                        and draft[key] in (None, [])],
            "unexpected_date_claim": reference["stated_dates"] is None and draft["stated_dates"] is not None,
            "reference_mismatches": [key for key, matched in fields.items() if not matched]}


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["method"], row["kind"])].append(row)
    summaries = []
    for (method, kind), group in sorted(grouped.items()):
        valid = [row for row in group if row["status"] == "ok"]
        summaries.append({"method": method, "kind": kind, "attempts": len(group),
                          "valid_outputs": len(valid), "failures": len(group) - len(valid),
                          "matched_fields": sum(row["score"]["matched_fields"] for row in valid),
                          "total_fields": len(group) * len(FIELDS),
                          "exact_cases": sum(row["score"]["exact_case"] for row in valid),
                          "unexpected_date_claims": sum(row["score"]["unexpected_date_claim"] for row in valid),
                          "citation_precision_mean": (sum(row["score"]["citation_precision"] for row in valid)
                                                      / len(valid)) if valid else None,
                          "citation_recall_mean": (sum(row["score"]["citation_recall"] for row in valid)
                                                   / len(valid)) if valid else None,
                          "elapsed_seconds": round(sum(row["elapsed_seconds"] for row in group), 3)})
    return summaries


def evaluate(cases, mode, models, max_requests=8, opener=urlopen, progress=None):
    if mode not in {"baseline", "live"}:
        raise ValueError("Choose baseline or live mode")
    if not cases or len(set(models)) != len(models):
        raise ValueError("Choose nonempty cases and unique model names")
    if not 1 <= max_requests <= 8:
        raise ValueError("Maximum model requests must be between 1 and 8")
    if "keyword_baseline" in models:
        raise ValueError("keyword_baseline is a reserved method name")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,100}", model) for model in models):
        raise ValueError("Invalid local model name")
    requests = len(cases) * len(models) if mode == "live" else 0
    if mode == "live" and not models:
        raise ValueError("Live mode requires at least one explicit model")
    if requests > max_requests:
        raise ValueError(f"Run needs {requests} model requests; limit is {max_requests}. No requests made.")
    rows = []
    for case in cases:
        methods = ["keyword_baseline"] + (models if mode == "live" else [])
        for method in methods:
            if progress:
                progress(f"{case['id']}: {method}")
            row = {"case_id": case["id"], "kind": case["kind"], "method": method,
                   "status": "failed", "draft": None, "requests_made": 0}
            started = perf_counter()
            try:
                if method == "keyword_baseline":
                    row["draft"] = keyword_baseline(case["input"])
                else:
                    row["requests_made"] = 1
                    result = extract_notice(case["input"], opener=opener, model=method)
                    row["draft"] = result["model_draft"]
                    row["diagnostics"] = result["diagnostics"]
                row["score"] = score_draft(row["draft"], case)
                row["status"] = "ok"
            except (RuntimeError, ValueError) as exc:
                row["error"] = str(exc)
            row["elapsed_seconds"] = round(perf_counter() - started, 3)
            rows.append(row)
    return rows


def markdown_report(report):
    lines = ["# Raw notice extraction evaluation", "", f"Mode: **{report['mode']}**. "
             f"Model requests: **{report['requests_made']}**. Generated: {report['generated_at']}.", "",
             "Raw model output is scored before reference-based UI correction. "
             "Field scores include failures in the denominator; citation averages cover valid outputs only.", "",
             "| Method | Evidence | Valid / attempted | Exact fields | Exact cases | Unexpected dates | Seconds |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in report["summary"]:
        lines.append(f"| {row['method']} | {row['kind']} | {row['valid_outputs']}/{row['attempts']} | "
                     f"{row['matched_fields']}/{row['total_fields']} | {row['exact_cases']}/{row['attempts']} | "
                     f"{row['unexpected_date_claims']} | {row['elapsed_seconds']} |")
    lines += ["", "## Individual results", ""]
    for row in report["results"]:
        lines += [f"### {row['case_id']} — {row['method']}", "", f"Status: {row['status']}."]
        if row["status"] != "ok":
            lines += [f"Error: {row['error']}", ""]
            continue
        score = row["score"]
        lines += [f"Reference mismatches: {', '.join(score['reference_mismatches']) or 'none'}.",
                  f"Citation precision/recall: {score['citation_precision']:.2f}/{score['citation_recall']:.2f}.",
                  f"Missing required fields: {', '.join(score['missing_required_fields']) or 'none'}.",
                  f"Unexpected date claim: {score['unexpected_date_claim']}.", "",
                  "```json", json.dumps(row["draft"], ensure_ascii=False, indent=2), "```", ""]
        diagnostics = row.get("diagnostics", {})
        if diagnostics:
            lines += [f"Model-reported tokens (prompt/output): {diagnostics.get('prompt_eval_count', 'unknown')}/"
                      f"{diagnostics.get('eval_count', 'unknown')}. Model digest: "
                      f"{diagnostics.get('model_digest') or 'not recorded'}. Raw reply is retained in results.json.", ""]
    lines += ["## Limits and interpretation", ""] + [f"- {item}" for item in LIMITATIONS]
    lines += ["", "## Next evidence to collect", "",
              "Have the teammate independently review reference fields and cited sentences; "
              "freeze a set of unseen public notices before changing the prompt. Compare review time "
              "and important missed/unsupported facts over repeated runs. Do not claim AI superiority "
              "or time savings from this small diagnostic set.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["baseline", "live"], default="baseline")
    parser.add_argument("--models", nargs="+", default=[])
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--max-requests", type=int, default=8)
    parser.add_argument("--output", required=True, type=Path, help="New output directory; existing output is never replaced")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        cases, manifest_hash = load_cases(root)
        if args.case_ids:
            unknown = set(args.case_ids) - {case["id"] for case in cases}
            if unknown:
                raise ValueError(f"Unknown case IDs: {sorted(unknown)}")
            cases = [case for case in cases if case["id"] in args.case_ids]
        if args.output.exists():
            raise ValueError("Choose a new output directory; existing results are preserved")
        rows = evaluate(cases, args.mode, args.models, args.max_requests,
                        progress=lambda message: print(message, flush=True))
        report = {"version": 1, "mode": args.mode,
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "manifest_sha256": manifest_hash,
                  "extractor_sha256": sha256((root / "harness/notice_draft.py").read_bytes()),
                  "evaluator_sha256": sha256(Path(__file__).read_bytes()),
                  "request_limits": {"maximum_requests": args.max_requests,
                                     "seconds_per_request": TIMEOUT_SECONDS, "retries": 0},
                  "requests_made": sum(row["requests_made"] for row in rows),
                  "cases": cases, "results": rows, "summary": summarize(rows), "limitations": LIMITATIONS}
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.output / "report.md").write_text(markdown_report(report), encoding="utf-8")
        print(f"Saved {args.output / 'report.md'}", flush=True)
        return 1 if any(row["status"] != "ok" for row in rows) else 0
    except (OSError, ValueError) as exc:
        print(f"Evaluation stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
