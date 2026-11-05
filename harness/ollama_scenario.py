"""Ask local Ollama for one checked scenario alternative."""

import argparse
import copy
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    from .scenario_compare import compare_scenario
except ImportError:
    from scenario_compare import compare_scenario


MODEL = "qwen2.5:3b"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 16 * 1024
CLOSURE_WORDS = ("close", "closure", "shut", "blocked", "stengt", "steng")
RESPONSE_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "kind": {"const": "clarifying_question"},
                "question": {"type": "string", "minLength": 1},
            },
            "required": ["kind", "question"],
            "additionalProperties": False,
        },
        {
            "properties": {
                "kind": {"const": "draft_alternative"},
                "alternative": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "label": {"type": "string", "minLength": 1},
                        "hypothetical": {"type": "boolean"},
                        "operations": {"type": "array", "minItems": 1},
                    },
                    "required": ["id", "operations"],
                    "additionalProperties": True,
                },
            },
            "required": ["kind", "alternative"],
            "additionalProperties": False,
        },
    ],
}
COMPARISON_RESPONSE_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "kind": {"const": "clarifying_question"},
                "question": {"type": "string", "minLength": 1},
            },
            "required": ["kind", "question"],
            "additionalProperties": False,
        },
        {
            "properties": {
                "kind": {"const": "comparison_draft"},
                "rationale": {"type": "string", "minLength": 1},
                "options": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {
                        "type": "object",
                        "properties": {
                            "candidate_id": {"type": "string", "minLength": 1},
                            "reason": {"type": "string", "minLength": 1},
                        },
                        "required": ["candidate_id", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["kind", "rationale", "options"],
            "additionalProperties": False,
        },
    ],
}


def _prompt(
    scenario, question, closure_mode, comparison=False, closure_links=None,
    checked_effects=None,
):
    candidates = scenario.get("candidates", [])
    if comparison:
        link_ids = list(closure_links or [])
        nodes = sorted({
            endpoint
            for candidate in candidates
            for endpoint in (candidate["from"], candidate["to"])
        } | set(
            endpoint
            for link in scenario["network"]
            if link["id"] in link_ids
            for endpoint in (link["from"], link["to"])
        ))
    else:
        link_ids = [link["id"] for link in scenario["network"]]
        nodes = sorted({
            endpoint
            for link in scenario["network"]
            for endpoint in (link["from"], link["to"])
        })
    candidate_text = json.dumps([
        {
            "id": candidate["id"],
            "from": candidate["from"],
            "to": candidate["to"],
            "metres": candidate["metres"],
            "assumption": candidate["assumption"],
            "site_check": candidate.get("site_check", "Site check required."),
        }
        for candidate in candidates
    ])
    comparison_instruction = ""
    if comparison:
        comparison_instruction = f"""
Confirmed pedestrian closure link IDs: {json.dumps(closure_links)}
Select exactly two distinct candidate IDs from this list, with one short reason per choice:
{candidate_text}
Python-checked effects under that closure: {json.dumps(checked_effects, separators=(",", ":"))}
Return {{"kind":"comparison_draft","rationale":"...","options":[{{"candidate_id":"...","reason":"..."}},{{"candidate_id":"...","reason":"..."}}]}}.
Do not return operations and do not alter the confirmed closure."""
    return f"""You are a transport planning assistant. Return exactly one JSON object.
Known link IDs: {json.dumps(link_ids)}
Known node IDs: {json.dumps(nodes)}
Permitted operations: close_links with mode walking or vehicle, restrict_links with mode vehicle, and add_links.
Any add_links connection must be hypothetical and its metres must be an assumption.
If an essential detail is missing, return {{"kind":"clarifying_question","question":"..."}}.
Otherwise return {{"kind":"draft_alternative","alternative":{{...}}}}.
Example draft: {{"kind":"draft_alternative","alternative":{{"id":"pedestrian-detour","hypothetical":true,"operations":[{{"type":"close_links","mode":"walking","link_ids":["known-link"]}}]}}}}
The alternative must use only known IDs. Do not change the baseline network or journeys.
Planner-confirmed closure mode: {closure_mode}
{comparison_instruction}
Planner question: {question}"""


def _request(prompt, opener=urlopen, response_schema=RESPONSE_SCHEMA):
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": response_schema,
        "options": {"num_predict": 700},
    }).encode("utf-8")
    request = Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Ollama unavailable: {exc}") from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Ollama response exceeded the size limit")
    try:
        envelope = json.loads(payload)
        decoded = json.loads(envelope["response"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Malformed Ollama response: {exc}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("Malformed Ollama response: decoded reply must be a JSON object")
    return decoded


def _scope_question(question):
    lowered = question.lower()
    if any(word in lowered for word in CLOSURE_WORDS):
        return "Does the proposed closure apply to pedestrians, vehicles, or both?"
    return None


def _validate_scope(alternative, closure_mode):
    operations = alternative.get("operations")
    if not isinstance(operations, list):
        raise ValueError("model alternative operations must be a list")
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("model alternative operations must be objects")
        operation_type = operation.get("type")
        if operation_type == "close_links" and operation.get("mode") != closure_mode:
            raise ValueError(
                f"model closure mode conflicts with confirmed {closure_mode} scope"
            )
        if operation_type == "restrict_links" and closure_mode != "vehicle":
            raise ValueError(
                "model vehicle restriction conflicts with confirmed walking scope"
            )
        if operation_type == "add_links":
            links = operation.get("links")
            if not isinstance(links, list) or not all(isinstance(link, dict) for link in links):
                raise ValueError("model add_links links must be objects")
            if alternative.get("hypothetical") is not True:
                raise ValueError("model added links require hypothetical true")
            for link in links:
                if (
                    link.get("length_basis") != "assumption"
                    or not isinstance(link.get("assumption"), str)
                    or not link["assumption"].strip()
                ):
                    raise ValueError(
                        "model added link metres require an explicit assumption"
                    )


def run(scenario, question, closure_mode=None, opener=urlopen):
    clarification = _scope_question(question) if closure_mode is None else None
    if clarification:
        return {"kind": "clarifying_question", "question": clarification, "comparison": None}
    proposal = _request(_prompt(scenario, question, closure_mode), opener)
    if not isinstance(proposal, dict):
        raise ValueError("model response must be a JSON object")
    if proposal.get("kind") == "clarifying_question":
        if not isinstance(proposal.get("question"), str) or not proposal["question"].strip():
            raise ValueError("model clarification question is missing")
        return {"kind": "clarifying_question", "question": proposal["question"], "comparison": None}
    if proposal.get("kind") != "draft_alternative" or not isinstance(
        proposal.get("alternative"), dict
    ):
        raise ValueError("model response must contain one draft_alternative or clarifying_question")
    alternative = proposal["alternative"]
    operations = alternative.get("operations")
    if not isinstance(operations, list):
        raise ValueError("model alternative operations must be a list")
    if any(
        not isinstance(operation, dict)
        for operation in operations
    ):
        raise ValueError("model alternative operations must be objects")
    has_scope_operation = any(
        operation.get("type") in {"close_links", "restrict_links"}
        for operation in operations
    )
    if closure_mode is None and has_scope_operation:
        return {
            "kind": "clarifying_question",
            "question": "Does the proposed closure apply to pedestrians, vehicles, or both?",
            "comparison": None,
        }
    _validate_scope(alternative, closure_mode)
    checked_scenario = dict(scenario)
    checked_alternative = copy.deepcopy(alternative)
    checked_alternative["hypothetical"] = True
    checked_scenario["alternatives"] = [checked_alternative]
    comparison = compare_scenario(checked_scenario)
    return {
        "kind": "draft_alternative",
        "proposal": alternative,
        "comparison": comparison,
    }


def _candidate_comparison(scenario, closure_links, candidate):
    option_scenario = dict(scenario)
    option_scenario["alternatives"] = [{
    "id": f"candidate-{candidate['id']}",
    "hypothetical": True,
    "operations": [
        {
            "type": "close_links",
            "mode": "walking",
            "link_ids": closure_links,
        },
        {
            "type": "add_links",
            "links": [{
                **candidate,
                "modes": ["walking"],
                "length_basis": "assumption",
            }],
        },
    ],
    }]
    return compare_scenario(option_scenario)["alternatives"][0]


def _checked_candidate_effects(scenario, closure_links):
    baseline_scenario = dict(scenario)
    baseline_scenario["alternatives"] = [{
    "id": "closure-only",
    "hypothetical": True,
    "operations": [{
        "type": "close_links", "mode": "walking", "link_ids": closure_links
    }]
    }]
    closure_only = compare_scenario(baseline_scenario)
    baseline = closure_only["baseline"]
    closure = closure_only["alternatives"][0]
    effects = []
    for candidate in scenario["candidates"]:
        candidate_result = _candidate_comparison(scenario, closure_links, candidate)
        journeys = []
        for base, closed, option in zip(
            baseline, closure["journeys"], candidate_result["journeys"]
        ):
            base_route = base["route"]
            closed_route = closed["route"]
            option_route = option["route"]
            journeys.append({
                "journey_id": base["journey_id"],
                "candidate_id": candidate["id"],
                "assumed_metres": candidate["metres"],
                "baseline_metres": base_route["metres"],
                "closure_metres": closed_route["metres"],
                "candidate_metres": option_route["metres"],
                "access_restored": (
                    closed_route["metres"] is None and option_route["metres"] is not None
                ),
                "unreachable_after_closure": closed_route["metres"] is None,
                "unreachable_with_candidate": option_route["metres"] is None,
                "change_vs_baseline": (
                    None if option_route["metres"] is None else
                    option_route["metres"] - base_route["metres"]
                ),
                "change_vs_closure": (
                    None if option_route["metres"] is None or closed_route["metres"] is None
                    else option_route["metres"] - closed_route["metres"]
                ),
            })
        effects.append({
            "candidate_id": candidate["id"],
            "assumed_metres": candidate["metres"],
            "assumption": candidate["assumption"],
            "site_check": candidate.get("site_check", "Site check required."),
            "journeys": journeys,
        })
    return closure_only, effects


def _comparison_results(scenario, closure_links, selected, closure_only, effects):
    results = {
        "mode": closure_only["mode"],
        "scenario": closure_only["scenario"],
        "baseline": closure_only["baseline"],
        "alternatives": [closure_only["alternatives"][0]],
    }
    results["alternatives"][0]["closure_link_ids"] = list(closure_links)
    effect_by_id = {effect["candidate_id"]: effect for effect in effects}
    for index, choice in enumerate(selected):
        candidate = next(
            candidate for candidate in scenario["candidates"]
            if candidate["id"] == choice["candidate_id"]
        )
        option_result = _candidate_comparison(scenario, closure_links, candidate)
        option_result["id"] = f"option-{index + 1}"
        option_result["label"] = choice["candidate_id"]
        option_result["closure_link_ids"] = list(closure_links)
        results["alternatives"].append(option_result)
    return results, [effect_by_id[choice["candidate_id"]] for choice in selected]


def run_comparison(scenario, question, closure_mode, closure_links, opener=urlopen):
    if closure_mode != "walking":
        raise ValueError("comparison mode requires confirmed walking scope")
    if not isinstance(closure_links, list) or not closure_links:
        raise ValueError("comparison mode requires confirmed closure link IDs")
    link_ids = {link["id"] for link in scenario.get("network", [])}
    if any(link_id not in link_ids for link_id in closure_links):
        raise ValueError("confirmed closure contains an unknown link ID")
    candidates = scenario.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 3:
        raise ValueError("comparison scenario needs at least three candidates")
    candidate_ids = [candidate.get("id") for candidate in candidates]
    if len(set(candidate_ids)) != len(candidate_ids) or any(
        not isinstance(candidate_id, str) or not candidate_id
        for candidate_id in candidate_ids
    ):
        raise ValueError("candidate IDs must be unique non-empty strings")
    closure_only, effects = _checked_candidate_effects(scenario, closure_links)
    proposal = _request(
        _prompt(scenario, question, closure_mode, True, closure_links, effects),
        opener,
        COMPARISON_RESPONSE_SCHEMA,
    )
    if not isinstance(proposal, dict):
        raise ValueError("model response must be a JSON object")
    if proposal.get("kind") == "clarifying_question":
        if not isinstance(proposal.get("question"), str) or not proposal["question"].strip():
            raise ValueError("model clarification question is missing")
        return {"kind": "clarifying_question", "question": proposal["question"], "comparison": None}
    if proposal.get("kind") != "comparison_draft":
        raise ValueError("model response must contain one comparison_draft or clarifying_question")
    options = proposal.get("options")
    if not isinstance(options, list) or len(options) != 2:
        raise ValueError("model comparison options must contain exactly two choices")
    selected_ids = [option.get("candidate_id") if isinstance(option, dict) else None for option in options]
    if any(
        not isinstance(option, dict)
        or not isinstance(option.get("candidate_id"), str)
        or not isinstance(option.get("reason"), str)
        or not option["reason"].strip()
        for option in options
    ):
        raise ValueError("model comparison options must contain candidate IDs and reasons")
    if len(set(selected_ids)) != 2:
        raise ValueError("model comparison candidate IDs must be distinct")
    if any(candidate_id not in candidate_ids for candidate_id in selected_ids):
        raise ValueError("model comparison references an unknown candidate ID")
    if any("operations" in option or "link_ids" in option for option in options):
        raise ValueError("model options cannot alter the confirmed closure")
    comparison, selected_effects = _comparison_results(
        scenario, closure_links, options, closure_only, effects
    )
    return {
        "kind": "comparison_draft",
        "proposal": proposal,
        "comparison": comparison,
        "impact_summary": {
            "closure_only": closure_only["alternatives"][0]["journeys"],
            "selected_candidates": selected_effects,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--closure-mode", choices=("walking", "vehicle"))
    parser.add_argument("--closure-links", nargs="+")
    parser.add_argument("--compare-options", action="store_true")
    args = parser.parse_args()
    try:
        scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
        if args.compare_options:
            result = run_comparison(
                scenario, args.question, args.closure_mode, args.closure_links
            )
        else:
            result = run(scenario, args.question, args.closure_mode)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        parser.exit(1, f"Scenario workflow stopped: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
