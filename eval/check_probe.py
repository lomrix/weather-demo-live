"""Independently check an offline probe against the saved rule excerpt."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    fixture_path = ROOT / "fixtures" / "funding-timeline-rule.json"
    output_path = ROOT / "out" / "probe.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    output = json.loads(output_path.read_text(encoding="utf-8"))

    require(isinstance(fixture, dict), "Fixture must be a JSON object.")
    require(isinstance(output, dict), "Output must be a JSON object.")

    for field in ("rule_id", "source_url", "checked_on", "source_quote"):
        value = fixture.get(field)
        require(
            isinstance(value, str) and bool(value.strip()),
            f"Fixture {field} must be a non-empty string.",
        )

    source = urlsplit(fixture["source_url"])
    require(
        source.scheme == "https" and bool(source.hostname),
        "Fixture source_url must be an HTTPS URL with a host.",
    )
    try:
        checked_on = date.fromisoformat(fixture["checked_on"])
    except ValueError as error:
        raise ValueError("Fixture checked_on must be a valid ISO date (YYYY-MM-DD).") from error
    require(
        checked_on.isoformat() == fixture["checked_on"],
        "Fixture checked_on must use YYYY-MM-DD format.",
    )

    for field in ("source_url", "checked_on"):
        require(
            output.get(field) == fixture[field],
            f"Output {field} must equal the fixture value.",
        )

    items = output.get("items")
    require(isinstance(items, list), "Output items must be a list.")
    require(len(items) == 1, "Output items must contain exactly one item.")
    require(isinstance(items[0], dict), "Output item must be a JSON object.")
    for field in ("rule_id", "source_quote"):
        require(
            items[0].get(field) == fixture[field],
            f"Output item {field} must equal the fixture value unchanged.",
        )

    print("PASS")


if __name__ == "__main__":
    main()
