"""Render a checked Hamar comparison JSON as an offline browser page."""

import argparse
import json
import math
import sys
from html import escape
from pathlib import Path


def _route_text(metres):
    return "No route available" if metres is None else f"{metres:,} m"


def _journey_map(rows, label):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{label} journeys must be a non-empty list")
    mapped = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} journey must be an object")
        journey_id = row.get("journey_id")
        if not isinstance(journey_id, str) or not journey_id.strip():
            raise ValueError(f"{label} journey IDs must be non-empty strings")
        if journey_id in mapped:
            raise ValueError(f"{label} has duplicate journey ID {journey_id}")
        mapped[journey_id] = row
    return mapped


def _require_same_journey_ids(expected, actual, label):
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        raise ValueError(f"{label} is missing journey IDs: {sorted(missing)}")
    if unexpected:
        raise ValueError(f"{label} has unexpected journey IDs: {sorted(unexpected)}")


def _validate_comparison(result):
    if not isinstance(result, dict):
        raise ValueError("comparison result must be a JSON object")
    if result.get("kind") == "clarifying_question":
        question = result.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("clarifying question must be non-empty")
        return "clarification", result
    comparison = result.get("comparison")
    impact = result.get("impact_summary")
    if not isinstance(comparison, dict):
        raise ValueError("checked comparison is required")
    if impact is None:
        baseline = _journey_map(comparison.get("baseline"), "baseline")
        alternatives = comparison.get("alternatives")
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError("comparison alternatives are required")
        for alternative in alternatives:
            if not isinstance(alternative, dict):
                raise ValueError("comparison alternative must be an object")
            rows = _journey_map(
                alternative.get("journeys"), f"alternative {alternative.get('id', '')}"
            )
            _require_same_journey_ids(
                set(baseline), set(rows), f"alternative {alternative.get('id', '')}"
            )
        return "scenario", result
    if not isinstance(impact, dict):
        raise ValueError("impact_summary must be an object")
    scenario = comparison.get("scenario")
    if not isinstance(scenario, dict):
        raise ValueError("comparison scenario is required")
    closure_only = impact.get("closure_only")
    selected = impact.get("selected_candidates")
    if not isinstance(closure_only, list) or not closure_only:
        raise ValueError("impact_summary closure_only must be a non-empty list")
    if not isinstance(selected, list) or len(selected) < 2:
        raise ValueError("impact_summary needs two selected candidates")
    closure_map = _journey_map(closure_only, "closure_only")
    for journey in closure_only:
        if not isinstance(journey.get("baseline"), dict):
            raise ValueError("closure_only journeys need checked baseline routes")
        if not isinstance(journey.get("route"), dict):
            raise ValueError("closure_only journeys need checked routes")
    expected_ids = set(closure_map)
    for candidate in selected:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("candidate_id"), str):
            raise ValueError("selected candidates need IDs")
        if not isinstance(candidate.get("assumed_metres"), (int, float)):
            raise ValueError("selected candidates need assumed lengths")
        candidate_map = _journey_map(
            candidate.get("journeys"), f"candidate {candidate['candidate_id']}"
        )
        _require_same_journey_ids(
            expected_ids, set(candidate_map), f"candidate {candidate['candidate_id']}"
        )
        for journey in candidate_map.values():
            for field in ("baseline_metres", "closure_metres", "candidate_metres"):
                if journey.get(field) is not None and not isinstance(journey[field], (int, float)):
                    raise ValueError(f"candidate {candidate['candidate_id']} has invalid {field}")
    return "comparison", result


def _journey_card(title, body, class_name=""):
    return f'<article class="card {class_name}"><h3>{escape(title)}</h3>{body}</article>'


def _access_status(comparison_metres, prior_metres):
    if prior_metres is None:
        return "Access restored." if comparison_metres is not None else "Still unreachable."
    return "Access lost." if comparison_metres is None else "Still reachable."


def _route_map_section(comparison):
    scenario = comparison["scenario"]
    map_data = scenario.get("map_extract", {}).get("route_map")
    if not isinstance(map_data, dict):
        return ""
    coordinates = map_data.get("node_coordinates")
    context_links = map_data.get("context_links")
    baseline_rows = _journey_map(comparison["baseline"], "baseline")
    if not isinstance(coordinates, dict) or not isinstance(context_links, list):
        return (
            '<section class="route-map"><h2>Mapped route map</h2>'
            '<p>Route geometry unavailable: the saved map geometry is incomplete.</p></section>'
        )
    detour_id = map_data.get("detour_alternative_id")
    alternatives = comparison.get("alternatives", [])
    detour = next(
        (alternative for alternative in alternatives
         if alternative.get("id") == detour_id),
        None,
    )
    if detour is None:
        detour = next(
            (alternative for alternative in alternatives if alternative.get("hypothetical")),
            None,
        )
    if detour is None:
        return (
            '<section class="route-map"><h2>Mapped route map</h2>'
            '<p>Route geometry unavailable: no checked detour result was supplied.</p></section>'
        )
    detour_rows = _journey_map(detour.get("journeys"), "detour")
    journey_id = next(iter(baseline_rows))
    baseline_route = baseline_rows[journey_id].get("route")
    detour_route = detour_rows.get(journey_id, {}).get("route")
    baseline_path = baseline_route.get("path") if isinstance(baseline_route, dict) else None
    detour_path = detour_route.get("path") if isinstance(detour_route, dict) else None
    if not isinstance(baseline_path, list) or not isinstance(detour_path, list):
        return (
            '<section class="route-map"><h2>Mapped route map</h2>'
            '<p>Route geometry unavailable: a checked route has no mapped path.</p></section>'
        )
    needed = set(baseline_path) | set(detour_path)
    points = {}
    for node_id in needed:
        value = coordinates.get(node_id)
        if (
            not isinstance(value, list) or len(value) != 2
            or not all(isinstance(item, (int, float)) for item in value)
        ):
            return (
                '<section class="route-map"><h2>Mapped route map</h2>'
                f'<p>Route geometry unavailable: node {escape(str(node_id))} '
                "has no unambiguous coordinates.</p></section>"
            )
        points[node_id] = (value[1], value[0])
    for link in context_links:
        if not isinstance(link, dict):
            continue
        for node_id in (link.get("from"), link.get("to")):
            value = coordinates.get(node_id)
            if isinstance(value, list) and len(value) == 2:
                points[node_id] = (value[1], value[0])
    if len(points) < 2:
        return (
            '<section class="route-map"><h2>Mapped route map</h2>'
            '<p>Route geometry unavailable: fewer than two mapped points were saved.</p></section>'
        )
    min_x = min(point[0] for point in points.values())
    max_x = max(point[0] for point in points.values())
    min_y = min(point[1] for point in points.values())
    max_y = max(point[1] for point in points.values())
    width, height, padding = 900, 480, 28
    scale_x = (width - 2 * padding) / max(max_x - min_x, 0.00001)
    scale_y = (height - 2 * padding) / max(max_y - min_y, 0.00001)
    scale = min(scale_x, scale_y)

    def project(node_id):
        lon, lat = points[node_id]
        return (
            padding + (lon - min_x) * scale,
            height - padding - (lat - min_y) * scale,
        )

    def polyline(node_ids):
        return " ".join(
            f"{project(node_id)[0]:.1f},{project(node_id)[1]:.1f}"
            for node_id in node_ids if node_id in points
        )

    interruption_ids = set(
        scenario.get("map_extract", {}).get("interrupted_link", {}).get(
            "closure_segment_ids", []
        )
    )
    context = []
    interruption = []
    for link in context_links:
        if not isinstance(link, dict):
            continue
        start, end = link.get("from"), link.get("to")
        if start not in points or end not in points:
            continue
        line = f'<line x1="{project(start)[0]:.1f}" y1="{project(start)[1]:.1f}" '
        line += f'x2="{project(end)[0]:.1f}" y2="{project(end)[1]:.1f}"/>'
        (interruption if link.get("id") in interruption_ids else context).append(line)
    origin = baseline_path[0] if baseline_path else ""
    destination = baseline_path[-1] if baseline_path else ""
    markers = ""
    for node_id, label, css_class in (
        (origin, "Start", "start"),
        (destination, "Destination", "destination"),
    ):
        if node_id in points:
            x, y = project(node_id)
            markers += (
                f'<circle class="marker {css_class}" cx="{x:.1f}" cy="{y:.1f}" r="6"/>'
                f'<text x="{x + 9:.1f}" y="{y - 9:.1f}">{escape(label)}</text>'
            )
    controls = (
        '<label><input type="checkbox" data-layer="baseline" checked> Baseline</label>'
        '<label><input type="checkbox" data-layer="detour" checked> Detour</label>'
        '<label><input type="checkbox" data-layer="interruption" checked> Interrupted segment</label>'
    )
    return (
        '<section class="route-map"><h2>Mapped route map</h2>'
        '<p>Checked route geometry from the saved local OSM extract. '
        'Nearby mapped walking links are shown for context.</p>'
        f'<div class="map-controls">{controls}</div>'
        f'<svg class="route-map-svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Baseline and detour walking routes">'
        f'<g class="layer context">{"".join(context)}</g>'
        f'<polyline class="layer baseline" points="{polyline(baseline_path)}"/>'
        f'<polyline class="layer detour" points="{polyline(detour_path)}"/>'
        f'<g class="layer interruption">{"".join(interruption)}</g>'
        f'<g class="markers">{markers}</g></svg>'
        '<div class="map-legend"><span class="legend-line baseline-key">Baseline</span>'
        '<span class="legend-line detour-key">Detour</span>'
        '<span class="legend-line interruption-key">Interrupted segment</span>'
        '<span class="legend-context">Nearby mapped paths</span></div>'
        f'<p class="attribution">{escape(str(map_data.get("attribution", "OpenStreetMap contributors")))}</p>'
        '</section>'
        '<script>(function(){document.querySelectorAll(".map-controls input").forEach(function(input){'
        'input.addEventListener("change",function(){document.querySelectorAll("." + input.dataset.layer)'
        '.forEach(function(layer){layer.style.display=input.checked ? "" : "none";});});});})();</script>'
    )


def _comparison_route_map_section(comparison, selected):
    scenario = comparison["scenario"]
    map_data = scenario.get("map_extract", {}).get("route_map")
    if not isinstance(map_data, dict):
        return ""
    coordinates = map_data.get("node_coordinates")
    context_links = map_data.get("context_links")
    candidate_links = map_data.get("candidate_links", [])
    baseline_rows = _journey_map(comparison["baseline"], "baseline")
    if not isinstance(coordinates, dict) or not isinstance(context_links, list):
        return (
            '<section class="route-map"><h2>Mapped route map</h2>'
            '<p>Route geometry unavailable: the saved map geometry is incomplete.</p></section>'
        )
    alternatives = comparison.get("alternatives", [])
    if not alternatives:
        return (
            '<section class="route-map"><h2>Mapped route map</h2>'
            '<p>Route geometry unavailable: no checked alternatives were supplied.</p></section>'
        )
    journey_ids = list(baseline_rows)
    alternative_rows = [
        _journey_map(alternative.get("journeys"), f"alternative {alternative.get('id', '')}")
        for alternative in alternatives
    ]
    layers_by_journey = {}
    paths = []
    for journey_id in journey_ids:
        layers = [("route-baseline", "Baseline", baseline_rows[journey_id].get("route"))]
        for index, (alternative, rows) in enumerate(zip(alternatives, alternative_rows)):
            label = "Closure only" if index == 0 else str(
                alternative.get("label", alternative.get("id", "Option"))
            )
            layers.append((f"route-option-{index}", label, rows[journey_id].get("route")))
        for css_class, label, route in layers:
            if not isinstance(route, dict) or not isinstance(route.get("path"), list):
                return (
                    '<section class="route-map"><h2>Mapped route map</h2>'
                    f'<p>Route geometry unavailable: {escape(label)} has no mapped path '
                    f'for journey {escape(journey_id)}.</p></section>'
                )
            paths.append(route["path"])
        layers_by_journey[journey_id] = layers
    needed = set(node_id for path in paths for node_id in path)
    interruption_ids = set(
        scenario.get("map_extract", {}).get("interrupted_link", {}).get(
            "closure_segment_ids", []
        )
    )
    for link in context_links + candidate_links:
        if isinstance(link, dict):
            needed.update((link.get("from"), link.get("to")))
    points = {}
    for node_id in needed:
        value = coordinates.get(node_id)
        if (
            not isinstance(node_id, str)
            or not isinstance(value, list) or len(value) != 2
            or not all(isinstance(item, (int, float)) for item in value)
        ):
            return (
                '<section class="route-map"><h2>Mapped route map</h2>'
                f'<p>Route geometry unavailable: node {escape(str(node_id))} '
                "has no unambiguous coordinates.</p></section>"
            )
        points[node_id] = (value[1], value[0])
    if len(points) < 2:
        return (
            '<section class="route-map"><h2>Mapped route map</h2>'
            '<p>Route geometry unavailable: fewer than two mapped points were saved.</p></section>'
        )
    min_x = min(point[0] for point in points.values())
    max_x = max(point[0] for point in points.values())
    min_y = min(point[1] for point in points.values())
    max_y = max(point[1] for point in points.values())
    width, height, padding = 900, 480, 28
    scale = min(
        (width - 2 * padding) / max(max_x - min_x, 0.00001),
        (height - 2 * padding) / max(max_y - min_y, 0.00001),
    )

    def project(node_id):
        lon, lat = points[node_id]
        return padding + (lon - min_x) * scale, height - padding - (lat - min_y) * scale

    def polyline(node_ids):
        return " ".join(
            f"{project(node_id)[0]:.1f},{project(node_id)[1]:.1f}"
            for node_id in node_ids
        )

    context = []
    interruption = []
    for link in context_links:
        if not isinstance(link, dict) or link.get("from") not in points or link.get("to") not in points:
            continue
        start, end = link["from"], link["to"]
        line = (
            f'<line x1="{project(start)[0]:.1f}" y1="{project(start)[1]:.1f}" '
            f'x2="{project(end)[0]:.1f}" y2="{project(end)[1]:.1f}"/>'
        )
        (interruption if link.get("id") in interruption_ids else context).append(line)
    route_shapes = []
    controls = []
    legend = []
    for journey_index, journey_id in enumerate(journey_ids):
        for css_class, label, route in layers_by_journey[journey_id]:
            path = route["path"]
            route_shapes.append(
                f'<polyline class="layer {css_class}" data-journey="{escape(journey_id)}" '
                f'data-route-path="{escape(",".join(path))}" points="{polyline(path)}"/>'
            )
            if journey_index == 0:
                controls.append(
                    f'<label><input type="checkbox" data-layer="{css_class}" checked> '
                    f'{escape(label)}</label>'
                )
                legend.append(f'<span class="legend-line {css_class}-key">{escape(label)}</span>')
    selected_journey = journey_ids[0]
    journey_options = "".join(
        f'<option value="{escape(journey_id)}">{escape(journey_id)}</option>'
        for journey_id in journey_ids
    )
    markers = ""
    for journey_id in journey_ids:
        origin = layers_by_journey[journey_id][0][2]["path"][0]
        destination = layers_by_journey[journey_id][0][2]["path"][-1]
        x1, y1 = project(origin)
        x2, y2 = project(destination)
        markers += (
            f'<g class="markers" data-journey="{escape(journey_id)}">'
            f'<circle class="marker start" cx="{x1:.1f}" cy="{y1:.1f}" r="6"/>'
            f'<text x="{x1 + 9:.1f}" y="{y1 - 9:.1f}">Start</text>'
            f'<circle class="marker destination" cx="{x2:.1f}" cy="{y2:.1f}" r="6"/>'
            f'<text x="{x2 + 9:.1f}" y="{y2 - 9:.1f}">Destination</text></g>'
        )
    candidate_shapes = []
    selected_ids = {candidate["candidate_id"] for candidate in selected}
    for journey_id in journey_ids:
        for candidate in candidate_links:
            if not isinstance(candidate, dict) or candidate.get("id") not in selected_ids:
                continue
            start, end = candidate.get("from"), candidate.get("to")
            if start in points and end in points:
                candidate_shapes.append(
                    f'<line class="candidate-link" data-journey="{escape(journey_id)}" '
                    f'x1="{project(start)[0]:.1f}" y1="{project(start)[1]:.1f}" '
                    f'x2="{project(end)[0]:.1f}" y2="{project(end)[1]:.1f}"/>'
                )
    controls.insert(
        0,
        '<label>Journey on map: <select id="journey-selector">'
        f'{journey_options}</select></label>'
        f'<strong id="journey-map-status">Showing journey: {escape(selected_journey)}</strong>',
    )
    controls.append(
        '<label><input type="checkbox" data-layer="interruption" checked> '
        'Interrupted segment</label>'
    )
    controls.append(
        '<label><input type="checkbox" data-layer="candidate-link" checked> '
        'Selected proposed links</label>'
    )
    return (
        '<section class="route-map"><h2>Mapped route map</h2>'
        '<p>Checked baseline, closure and mitigation route geometry from the saved '
        'local OSM extract. Existing mapped paths and proposed links are distinct.</p>'
        f'<div class="map-controls">{"".join(controls)}</div>'
        f'<svg class="route-map-svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Baseline, closure and mitigation walking routes">'
        f'<g class="layer context">{"".join(context)}</g>'
        f'{"".join(route_shapes)}'
        f'<g class="layer interruption">{"".join(interruption)}</g>'
        f'<g class="layer candidate-link">{"".join(candidate_shapes)}</g>'
        f'{markers}</svg>'
        f'<div class="map-legend">{"".join(legend)}'
        '<span class="legend-line interruption-key">Interrupted segment</span>'
        '<span class="legend-line candidate-key">Selected proposed links</span>'
        '<span class="legend-context">Nearby mapped paths</span></div>'
        f'<p class="attribution">{escape(str(map_data.get("attribution", "OpenStreetMap contributors")))}</p>'
        '</section>'
        '<script>(function(){var selector=document.getElementById("journey-selector");'
        'var status=document.getElementById("journey-map-status");'
        'function refresh(){var journey=selector.value;'
        'document.querySelectorAll("[data-journey]").forEach(function(layer){'
        'var visible=layer.dataset.journey===journey;'
        'if(layer.dataset.layer){var input=document.querySelector(".map-controls input[data-layer=\'"+layer.dataset.layer+"\']");'
        'visible=visible && input.checked;} layer.style.display=visible ? "" : "none";});'
        'status.textContent="Showing journey: "+journey;}'
        'document.querySelectorAll(".map-controls input").forEach(function(input){input.addEventListener("change",refresh);});'
        'selector.addEventListener("change",refresh); refresh();})();</script>'
    )


def _comparison_page(result):
    comparison = result["comparison"]
    impact = result["impact_summary"]
    scenario = comparison["scenario"]
    closure_only = impact["closure_only"]
    selected = impact["selected_candidates"]
    draft = result.get("proposal")
    sections = []
    closure_map = _journey_map(closure_only, "closure_only")
    candidate_maps = {
        candidate["candidate_id"]: _journey_map(
            candidate["journeys"], f"candidate {candidate['candidate_id']}"
        )
        for candidate in selected
    }
    for closed in closure_only:
        journey_id = closed["journey_id"]
        baseline = closed["baseline"]
        baseline_metres = baseline["metres"]
        closure_metres = closed["route"]["metres"]
        cards = [
            _journey_card(
                "Baseline",
                f"<p class=\"distance\">{_route_text(baseline_metres)}</p>"
                f"<p>{escape(_access_status(baseline_metres, baseline_metres))}</p>",
            ),
            _journey_card(
                "Closure only",
                f"<p class=\"distance\">{_route_text(closure_metres)}</p>"
                f"<p>{escape(_access_status(closure_metres, baseline_metres))}</p>",
                "closure",
            ),
        ]
        for candidate in selected:
            checked = candidate_maps[candidate["candidate_id"]][journey_id]
            candidate_metres = checked["candidate_metres"]
            status = _access_status(candidate_metres, closure_metres)
            change = checked["change_vs_baseline"]
            closure_change = checked["change_vs_closure"]
            if change is None:
                change_text = "No reachable route to compare with baseline."
            elif change > 0:
                change_text = f"Added vs baseline ({baseline_metres:,} m): {change:,} m."
            elif change < 0:
                change_text = f"Saved vs baseline ({baseline_metres:,} m): {-change:,} m."
            else:
                change_text = f"Added vs baseline ({baseline_metres:,} m): 0 m."
            if closure_change is None:
                closure_change_text = "No reachable route to compare with closure."
            elif closure_change < 0:
                closure_change_text = f"Saved vs closure only ({closure_metres:,} m): {-closure_change:,} m."
            elif closure_change > 0:
                closure_change_text = f"Added vs closure only ({closure_metres:,} m): {closure_change:,} m."
            else:
                closure_change_text = f"Saved vs closure only ({closure_metres:,} m): 0 m."
            body = (
                f"<p class=\"distance\">{_route_text(candidate_metres)}</p>"
                f"<p>{escape(status)}</p>"
                f"<p>{escape(change_text)}</p>"
                f"<p>{escape(closure_change_text)}</p>"
                f"<p><strong>Candidate:</strong> {escape(candidate['candidate_id'])}<br>"
                f"<strong>Assumed length:</strong> {candidate['assumed_metres']:,} m<br>"
                f"<strong>Basis:</strong> {escape(candidate.get('assumption', 'Assumption'))}<br>"
                f"<strong>Site check:</strong> {escape(candidate.get('site_check', 'Required'))}</p>"
            )
            cards.append(_journey_card(candidate["candidate_id"], body, "option"))
        sections.append(
            f'<section class="journey"><h2>{escape(str(journey_id))}</h2>'
            f'<div class="grid">{"".join(cards)}</div></section>'
        )
    draft_section = ""
    if isinstance(draft, dict):
        reasons = []
        for option in draft.get("options", []):
            if isinstance(option, dict):
                reasons.append(
                    f"<li><strong>{escape(str(option.get('candidate_id', '')))}</strong>: "
                    f"{escape(str(option.get('reason', '')))}</li>"
                )
        draft_section = (
            '<details class="draft diagnostics"><summary>Raw Ollama diagnostics '
            '(unchecked)</summary>'
            f"<p>{escape(str(draft.get('rationale', '')))}</p>"
            f"<ul>{''.join(reasons)}</ul></details>"
        )
    sections.insert(0, _comparison_route_map_section(comparison, selected))
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hamar Access Lab comparison</title>
<style>
  * {{ box-sizing: border-box }}
  body {{ margin: 0; background: #edf4f2; color: #172f30; font: 1rem/1.45 system-ui, sans-serif }}
  main {{ max-width: 90rem; margin: auto; padding: clamp(1rem, 3vw, 2.5rem) }}
  h1 {{ font-size: clamp(2rem, 5vw, 3rem); line-height: 1.12; margin: .35rem 0 }}
  h2 {{ margin: 1.5rem 0 .6rem }}
  h3 {{ margin: 0; font-size: 1.05rem }}
  .eyebrow {{ color: #385d5a; font-weight: 650 }}
  .badge {{ display: inline-block; padding: .2rem .55rem; margin-right: .35rem; border-radius: 999px; background: #d7e9e5; font-size: .85rem; font-weight: 700 }}
  .grid {{ display: grid; grid-template-columns: repeat(4, minmax(13rem, 1fr)); gap: .75rem }}
  .card, .draft {{ background: white; padding: 1rem; border: 1px solid #bed1ce; border-radius: .7rem }}
  .route-map {{ background: white; padding: 1rem; border: 1px solid #bed1ce; border-radius: .7rem }}
  .route-map-svg {{ display: block; width: 100%; max-height: 34rem; background: #f7fbfa; border: 1px solid #d5e4e1; border-radius: .5rem }}
  .route-map-svg .context line {{ stroke: #b6c8c5; stroke-width: 1.2; opacity: .8 }}
  .route-map-svg .route-baseline {{ fill: none; stroke: #1769aa; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round }}
  .route-map-svg .route-option-0 {{ fill: none; stroke: #d9772b; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 8 5 }}
  .route-map-svg .route-option-1 {{ fill: none; stroke: #287c55; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round }}
  .route-map-svg .route-option-2 {{ fill: none; stroke: #7b4ab3; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 11 4 }}
  .route-map-svg .route-option-3 {{ fill: none; stroke: #9a5b16; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round }}
  .route-map-svg .interruption line {{ stroke: #b42318; stroke-width: 7; stroke-linecap: round }}
  .route-map-svg .candidate-link {{ stroke: #287c55; stroke-width: 7; stroke-dasharray: 5 5 }}
  .route-map-svg text {{ fill: #172f30; font-size: 13px; font-weight: 700 }}
  .marker {{ stroke: white; stroke-width: 2 }}
  .marker.start {{ fill: #1769aa }}
  .marker.destination {{ fill: #7b4ab3 }}
  .map-controls, .map-legend {{ display: flex; flex-wrap: wrap; gap: .75rem; margin: .75rem 0 }}
  .map-controls label {{ font-weight: 650 }}
  .legend-line, .legend-context {{ display: inline-flex; align-items: center; gap: .35rem; margin-right: .8rem }}
  .legend-line::before, .legend-context::before {{ content: ""; display: inline-block; width: 1.8rem; border-top: 4px solid }}
  .route-baseline-key::before {{ border-color: #1769aa }}
  .route-option-0-key::before {{ border-color: #d9772b; border-top-style: dashed }}
  .route-option-1-key::before {{ border-color: #287c55 }}
  .route-option-2-key::before {{ border-color: #7b4ab3; border-top-style: dashed }}
  .route-option-3-key::before {{ border-color: #9a5b16 }}
  .interruption-key::before {{ border-color: #b42318; border-top-width: 7px }}
  .candidate-key::before {{ border-color: #287c55; border-top-width: 7px; border-top-style: dashed }}
  .legend-context::before {{ border-color: #b6c8c5; border-top-width: 2px }}
  .attribution {{ color: #385d5a; font-size: .9rem }}
  .diagnostics {{ margin-top: 1.5rem; border-left: .35rem solid #806b9b }}
  .diagnostics summary {{ cursor: pointer; font-weight: 700 }}
  .closure {{ border-color: #c79672 }}
  .option {{ border-color: #6b9b91 }}
  .distance {{ font-size: 1.65rem; font-weight: 750; margin: .55rem 0 }}
  .draft {{ margin-top: 1.5rem; border-left: .35rem solid #806b9b }}
  .draft h2 {{ margin-top: 0 }}
  @media (max-width: 60rem) {{ .grid {{ grid-template-columns: repeat(2, minmax(13rem, 1fr)) }} }}
  @media (max-width: 36rem) {{ .grid {{ grid-template-columns: 1fr }} }}
</style>
<main>
  <header>
    <p class="eyebrow">Group 12 · Hamar Access Lab · Offline saved result</p>
    <span class="badge">{escape("Synthetic case" if scenario.get("synthetic") else "Real-data case")}</span><span class="badge">Hypothetical changes</span>
    <h1>{escape(str(scenario.get("label", scenario.get("id", "Comparison"))))}</h1>
    <p>Python-checked impacts are shown below. Temporary connection lengths are assumptions.</p>
  </header>
  {"".join(sections)}
  {draft_section}
</main>
</html>
"""


def _scenario_page(result):
    comparison = result["comparison"]
    scenario = comparison["scenario"]
    baseline = _journey_map(comparison["baseline"], "baseline")
    alternatives = comparison["alternatives"]
    alternative_maps = [
        (alternative, _journey_map(
            alternative["journeys"], f"alternative {alternative.get('id', '')}"
        ))
        for alternative in alternatives
    ]
    sections = []
    for journey_id, base in baseline.items():
        base_metres = base["route"]["metres"]
        cards = [_journey_card(
            "Baseline",
            f"<p class=\"distance\">{_route_text(base_metres)}</p>"
            f"<p>{escape(_access_status(base_metres, base_metres))}</p>",
        )]
        for alternative, rows in alternative_maps:
            route = rows[journey_id]["route"]
            metres = route["metres"]
            change = None if metres is None else metres - base_metres
            change_text = (
                "No reachable route to compare with baseline."
                if change is None else f"{change:+,} m versus baseline."
            )
            cards.append(_journey_card(
                alternative.get("label", alternative.get("id", "Alternative")),
                f"<p class=\"distance\">{_route_text(metres)}</p>"
                f"<p>{escape(_access_status(metres, base_metres))}</p>"
                f"<p>{escape(change_text)}</p>",
                "option" if alternative.get("hypothetical") else "closure",
            ))
        sections.append(
            f'<section class="journey"><h2>{escape(str(journey_id))}</h2>'
            f'<div class="grid">{"".join(cards)}</div></section>'
        )
    unknowns = scenario.get("unknowns", [])
    map_extract = scenario.get("map_extract", {})
    alternative_finding = map_extract.get("alternative_finding")
    if not alternative_finding:
        walking_alternatives = [
            alternative for alternative in alternatives
            if alternative.get("id") == "hypothetical-pedestrian-interruption"
        ]
        if walking_alternatives:
            has_detour = any(
                journey["route"]["metres"] is not None
                for journey in walking_alternatives[0]["journeys"]
            )
            alternative_finding = (
                "Detour found in checked walking comparison"
                if has_detour else
                "No detour found in checked walking comparison"
            )
    finding = (
        f"<p><strong>Detour check:</strong> {escape(str(alternative_finding))}</p>"
        if alternative_finding else ""
    )
    modeled_note = scenario.get("modeled_scenario_note")
    modeled = (
        f"<p><strong>Scenario note:</strong> {escape(str(modeled_note))}</p>"
        if modeled_note else ""
    )
    extract = (
        f"<p><strong>Map extract:</strong> "
        f"<a href=\"{escape(str(map_extract.get('url', '')))}\">public API query</a> "
        f"(retrieved {escape(str(map_extract.get('retrieved_at', 'unknown')))}).</p>"
        f"<p><strong>Origin:</strong> mapped crossing "
        f"{escape(str(map_extract.get('origin', {}).get('node_id', 'unknown')))} "
        f"at {escape(str(map_extract.get('origin', {}).get('coordinates', 'unknown')))}. "
        f"<strong>Interrupted way:</strong> "
        f"{escape(str(map_extract.get('interrupted_link', {}).get('way_id', 'unknown')))}. "
        f"<strong>Destination:</strong> mapped path node "
        f"{escape(str(map_extract.get('destination', {}).get('node_id', 'unknown')))}.</p>"
        if map_extract else ""
    )
    evidence = (
        "<section class=\"evidence\"><h2>Evidence and gaps</h2>"
        f"<p>Planning case: {escape(str(scenario.get('planning_case', 'Not stated')))}</p>"
        f"{modeled}{extract}{finding}"
        f"<ul>{''.join(f'<li>{escape(str(item))}</li>' for item in unknowns)}</ul>"
        "</section>"
    )
    sections.insert(0, _route_map_section(comparison))
    badge = "Synthetic case" if scenario.get("synthetic") else "Real-data case"
    return _scenario_document(
        scenario, badge, sections, evidence, "Hamar Access Lab comparison"
    )


def _scenario_document(scenario, badge, sections, evidence, title):
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
  * {{ box-sizing: border-box }}
  body {{ margin: 0; background: #edf4f2; color: #172f30; font: 1rem/1.45 system-ui, sans-serif }}
  main {{ max-width: 90rem; margin: auto; padding: clamp(1rem, 3vw, 2.5rem) }}
  h1 {{ font-size: clamp(2rem, 5vw, 3rem); line-height: 1.12; margin: .35rem 0 }}
  h2 {{ margin: 1.5rem 0 .6rem }}
  h3 {{ margin: 0; font-size: 1.05rem }}
  .eyebrow {{ color: #385d5a; font-weight: 650 }}
  .badge {{ display: inline-block; padding: .2rem .55rem; margin-right: .35rem; border-radius: 999px; background: #d7e9e5; font-size: .85rem; font-weight: 700 }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: .75rem }}
  .card, .evidence {{ background: white; padding: 1rem; border: 1px solid #bed1ce; border-radius: .7rem }}
  .route-map {{ background: white; padding: 1rem; border: 1px solid #bed1ce; border-radius: .7rem }}
  .route-map-svg {{ display: block; width: 100%; max-height: 34rem; background: #f7fbfa; border: 1px solid #d5e4e1; border-radius: .5rem }}
  .route-map-svg .context line {{ stroke: #b6c8c5; stroke-width: 1.2; opacity: .8 }}
  .route-map-svg .baseline {{ fill: none; stroke: #1769aa; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round }}
  .route-map-svg .detour {{ fill: none; stroke: #d9772b; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 8 5 }}
  .route-map-svg .interruption line {{ stroke: #b42318; stroke-width: 7; stroke-linecap: round }}
  .route-map-svg text {{ fill: #172f30; font-size: 13px; font-weight: 700 }}
  .marker {{ stroke: white; stroke-width: 2 }}
  .marker.start {{ fill: #1769aa }}
  .marker.destination {{ fill: #7b4ab3 }}
  .map-controls, .map-legend {{ display: flex; flex-wrap: wrap; gap: .75rem; margin: .75rem 0 }}
  .map-controls label {{ font-weight: 650 }}
  .legend-line, .legend-context {{ display: inline-flex; align-items: center; gap: .35rem; margin-right: .8rem }}
  .legend-line::before, .legend-context::before {{ content: ""; display: inline-block; width: 1.8rem; border-top: 4px solid }}
  .baseline-key::before {{ border-color: #1769aa }}
  .detour-key::before {{ border-color: #d9772b; border-top-style: dashed }}
  .interruption-key::before {{ border-color: #b42318; border-top-width: 7px }}
  .legend-context::before {{ border-color: #b6c8c5; border-top-width: 2px }}
  .attribution {{ color: #385d5a; font-size: .9rem }}
  .closure {{ border-color: #c79672 }}
  .option {{ border-color: #6b9b91 }}
  .distance {{ font-size: 1.65rem; font-weight: 750; margin: .55rem 0 }}
  @media (max-width: 36rem) {{ .grid {{ grid-template-columns: 1fr }} }}
</style>
<main>
  <header>
    <p class="eyebrow">Group 12 · Hamar Access Lab · Offline saved result</p>
    <span class="badge">{escape(badge)}</span><span class="badge">Hypothetical options are labelled</span>
    <h1>{escape(str(scenario.get("label", scenario.get("id", "Comparison"))))}</h1>
    <p>Python-checked impacts are shown below. Mapped links and documented gaps remain separate from hypothetical changes.</p>
  </header>
  {"".join(sections)}
  {evidence}
</main>
</html>
"""


def _clarification_page(result):
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hamar Access Lab clarification</title>
<body><main><h1>Clarification needed</h1>
<p>{escape(result["question"])}</p>
<p>No route comparison was calculated.</p></main></body></html>"""


def render(result):
    kind, checked = _validate_comparison(result)
    if kind == "clarification":
        return _clarification_page(checked)
    return _scenario_page(checked) if kind == "scenario" else _comparison_page(checked)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="HTML output path")
    args = parser.parse_args()
    try:
        text = sys.stdin.read().lstrip("\ufeff")
        page = render(json.loads(text))
    except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        parser.exit(1, f"Comparison page stopped. Expected checked comparison JSON. {exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print(args.output)
