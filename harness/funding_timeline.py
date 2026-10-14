"""Check whether a timeline is declared prepared against a saved rule."""

import json


def check_timeline(timeline_prepared, rule_path):
    """Return a preparation status and the rule's source URL.

    declared_present does not verify the timeline's contents or establish
    funding eligibility. File and JSON errors propagate to the caller.
    """
    if timeline_prepared is False:
        status = "missing"
    elif timeline_prepared is True:
        status = "declared_present"
    elif timeline_prepared is None:
        status = "unknown"
    else:
        raise ValueError("timeline_prepared must be False, True, or None")

    with open(rule_path, encoding="utf-8") as rule_file:
        rule = json.load(rule_file)

    return {"status": status, "source_url": rule["source_url"]}
