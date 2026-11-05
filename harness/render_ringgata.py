"""Render successful Ringgata replay JSON as a local browser page."""

import json
import sys
import argparse
from html import escape
from pathlib import Path


def route_card(label, route):
    if route["metres"] is None:
        return f"<article><h2>{label}</h2><p>No route available</p></article>"
    steps = "".join(f"<li>{escape(node)}</li>" for node in route["path"])
    return f"""<article><h2>{label}</h2>
<p class="distance">{route['metres']:,} m</p>
<ol class="route">{steps}</ol></article>"""


def render(result):
    comparison = result["comparison"]
    notice = result["notice"]
    bus = result["transport_context"]
    totals = bus["totals"]
    extra = comparison["extra_metres"]
    difference = "No route available after closure" if extra is None else f"{extra:+,} m after closure"
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ringgata walking detour</title>
<style>
  * {{ box-sizing: border-box }}
  body {{ margin: 0; background: #edf4f2; color: #172f30; font: 1rem/1.45 system-ui, sans-serif }}
  main {{ max-width: 68rem; margin: auto; padding: clamp(1rem, 3vw, 2.5rem) }}
  h1 {{ font-size: clamp(2rem, 5vw, 3rem); line-height: 1.12; margin: .35rem 0 }}
  h2 {{ font-size: 1.05rem; margin: 0 }}
  p {{ margin: .45rem 0 }}
  .eyebrow {{ color: #385d5a; font-weight: 650 }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr)); gap: .85rem; margin: .85rem 0 }}
  article {{ background: white; padding: 1rem 1.25rem; border: 1px solid #bed1ce; border-radius: .7rem }}
  .distance {{ font-size: 2rem; font-weight: 750; margin: 0 }}
  .delta {{ background: #153f40; color: white; padding: .55rem 1rem; border-radius: .5rem; font-weight: 700 }}
  .route {{ display: flex; flex-wrap: wrap; gap: .3rem 1.4rem; padding-left: 1.4rem; margin: .4rem 0 }}
  .route li::marker {{ color: #306764; font-weight: 700 }}
  a {{ color: #175651; text-underline-offset: .15em }}
</style>
<main>
  <header>
    <p class="eyebrow">Group 12 · Hamar · Offline replay</p>
    <h1>Ringgata walking detour</h1>
    <p>One walking journey to the illustrative demo bus stop.</p>
    <p><strong>Closure is hypothetical.</strong> Walking links, stop and distances are illustrative.</p>
  </header>
  <section class="grid" aria-label="Walking route comparison">
    {route_card("Baseline", comparison["baseline"])}
    {route_card("With crossing closed", comparison["crossing_closed"])}
  </section>
  <p class="delta">{difference}</p>
  <section class="grid" aria-label="Sources and evidence">
    <article>
      <h2>Official planning notice</h2>
      <p>Planning has started for a cycleway and pavement between Solvangvegen and Disenvegen.</p>
      <p lang="nb">“{escape(notice["proposal"]["evidence"])}”</p>
      <a href="{escape(notice["source_url"])}">Read the Hamar municipality notice</a>
    </article>
    <article>
      <h2>Saved Entur observations</h2>
      <p>{escape(", ".join(bus["service_dates"]))} · {escape(", ".join(bus["routes"]))}</p>
      <p>{totals["calls"]} stop calls · {totals["actual"]} actual · {totals["prediction_only"]} prediction-only</p>
      <p>Geographic link to Ringgata is unverified.</p>
      <a href="{escape(bus["source"]["source_url"])}">Entur source endpoint</a>
    </article>
  </section>
</main>
</html>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="HTML output path")
    args = parser.parse_args()
    try:
        page = render(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"Preview stopped. Expected a successful demo JSON replay. {exc}\n")
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(output)
