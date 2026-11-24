"""Build the Hamar area feed from reviewed, local source revisions."""

import hashlib
import json
from datetime import date, datetime
from urllib.parse import urlsplit


STATUSES = {
    "works_scheduled", "works_upcoming", "works_started",
    "closure_announced", "closure_active", "reopened",
}


def planned_period(revision):
    return tuple(revision.get(key) for key in ("start_date", "end_date", "period"))


def notice_feed(root, today=None):
    today = today if today is not None else date.today()
    records = json.loads(
        (root / "fixtures/notices/hamar-area.json").read_text(encoding="utf-8")
    )
    notices = []
    for record in records:
        revisions = record["revisions"]
        latest = revisions[-1]
        start, end, _ = planned_period(latest)
        start_day = date.fromisoformat(start) if start else None
        end_day = date.fromisoformat(end) if end else None
        source = urlsplit(record["source_url"] or "")
        if (latest["status"] not in STATUSES or not latest["evidence"].strip()
                or latest.get("evidence_kind", "note") not in {"quote", "summary", "note"}
                or (start_day and end_day and end_day < start_day)
                or (not record["synthetic"]
                    and (source.scheme, source.netloc) != ("https", "www.hamar.kommune.no"))):
            raise ValueError("Invalid reviewed notice")
        expired = bool(
            end_day and latest["status"] in {"closure_announced", "closure_active"}
            and end_day < today
        )
        # Collapse unchanged checks, even when the source-check timestamp advanced.
        facts = {key: value for key, value in latest.items() if key != "last_checked"}
        previous = next(
            (item for item in reversed(revisions[:-1])
             if planned_period(item) != planned_period(latest)),
            None,
        )
        changed = previous is not None and latest["status"] != "reopened"
        last_checked = latest["last_checked"]
        datetime.fromisoformat(last_checked)
        context = {key: value for key, value in record.items() if key != "revisions"}
        event = {
            **context, **facts, "evidence_kind": latest.get("evidence_kind", "note"), "reopening_unconfirmed": expired,
            "previous_period": {
                "start_date": previous.get("start_date"), "end_date": previous.get("end_date"),
                "period": previous.get("period"),
                "evidence": previous["evidence"], "evidence_kind": previous.get("evidence_kind", "note"),
                "last_checked": previous["last_checked"],
            } if changed else None,
            "modeled": False,
        }
        # A repeated check preserves read/dismiss state. A material update gets its own key.
        identity = {**event, "previous_period": {
            key: value for key, value in (event["previous_period"] or {}).items()
            if key != "last_checked"
        }}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        notices.append({**event, "event_id": digest, "last_checked": last_checked})
    if len({item["id"] for item in notices}) != len(notices):
        raise ValueError("Duplicate notice ID")
    return sorted(notices, key=lambda item: (item["last_checked"], item["id"]), reverse=True)
