"""Copy a saved funding-rule excerpt into an offline probe record."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


def write_probe(input_path, output_path):
    """Validate UTF-8 JSON input, then write its source values unchanged."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    rule = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(rule, dict):
        raise ValueError("Input must be a JSON object.")

    for field in ("source_url", "checked_on", "rule_id", "source_quote"):
        value = rule.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Input {field} must be a non-empty string.")

    source = urlsplit(rule["source_url"])
    if source.scheme != "https" or not source.hostname:
        raise ValueError("Input source_url must be an HTTPS URL with a host.")

    try:
        checked_on = date.fromisoformat(rule["checked_on"])
    except ValueError as error:
        raise ValueError("Input checked_on must be a valid ISO date (YYYY-MM-DD).") from error
    if checked_on.isoformat() != rule["checked_on"]:
        raise ValueError("Input checked_on must use YYYY-MM-DD format.")

    probe = {
        "source_url": rule["source_url"],
        "checked_on": rule["checked_on"],
        "items": [
            {
                "rule_id": rule["rule_id"],
                "source_quote": rule["source_quote"],
            }
        ],
    }
    serialized = json.dumps(probe, ensure_ascii=False, indent=2) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialized, encoding="utf-8")


def main():
    root = Path(__file__).resolve().parent.parent
    write_probe(
        root / "fixtures" / "funding-timeline-rule.json",
        root / "out" / "probe.json",
    )


if __name__ == "__main__":
    main()
