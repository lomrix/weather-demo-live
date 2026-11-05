"""Deterministic checks. Exact text matching shows a passage appears in the
extract. It does not show that the passage supports the claim."""
import re
from datetime import date
from urllib.parse import urlparse

FIELDS = ["proposal", "location", "planning_stage", "deadline", "participation", "response_route"]
MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli",
          "august", "september", "oktober", "november", "desember"]
SUSPICIOUS = re.compile(r"ignor|instruks|ignore|system prompt|forget", re.I)
ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def date_forms(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return {f"{d}. {MONTHS[m-1]} {y}", f"{d:02d}.{m:02d}.{y}", f"{d}.{m}.{y}"}


def check(facts, extract, meta):
    """Return (errors, warnings). Errors block saving a draft."""
    errors, warnings = [], []
    if not isinstance(meta, dict):
        return ["malformed metadata"], warnings
    for k in ("source_url", "retrieved_at"):
        if not meta.get(k):
            errors.append(f"missing provenance: {k}")
    try:
        url = urlparse(meta.get("source_url", "") if isinstance(meta.get("source_url"), str) else "")
        valid_url = url.scheme == "https" and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        valid_url = False
    if not valid_url:
        errors.append("source_url must be an absolute HTTPS URL")
    try:
        retrieved = meta.get("retrieved_at", "")
        if not isinstance(retrieved, str) or not ISO.fullmatch(retrieved):
            raise ValueError("date format")
        date.fromisoformat(retrieved)
    except (TypeError, ValueError):
        errors.append("retrieved_at must be an ISO date")
    if not isinstance(facts, dict) or not isinstance(facts.get("in_scope"), bool):
        return errors + ["malformed: in_scope must be a boolean"], warnings
    if not facts["in_scope"]:
        return errors, warnings
    text = norm(extract)
    if SUSPICIOUS.search(extract):
        warnings.append("extract contains instruction-like text, inspect the source")
    for f in FIELDS:
        v = facts.get(f)
        if not isinstance(v, dict) or not isinstance(v.get("value"), str) or not isinstance(v.get("evidence"), str):
            errors.append(f"malformed field: {f}")
            continue
        ev = v["evidence"]
        if not v['value'].strip():
            errors.append(f"{f}: empty value must be unknown or ambiguous")
        if not ev and v['value'] not in ('unknown', 'ambiguous'):
            errors.append(f"{f}: claim without evidence")
        elif ev and not re.search(r"(?<!\d)" + re.escape(norm(ev)) + r"(?!\d)", text):
            errors.append(f"{f}: evidence not found in extract")
    d = facts.get("deadline", {})
    if isinstance(d, dict) and isinstance(d.get("value"), str) and isinstance(d.get("evidence"), str) and d.get("value") not in ("unknown", "ambiguous"):
        m = ISO.match(d["value"])
        if not m:
            errors.append("deadline: not an ISO date, unknown or ambiguous")
        else:
            try:
                date(int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                errors.append("deadline: impossible date")
            else:
                if not any(re.search(r"(?<!\d)" + re.escape(norm(x)) + r"(?!\d)",
                                     norm(d.get("evidence", "")))
                           for x in date_forms(d["value"])):
                    errors.append("deadline: date not stated in its evidence")
    return errors, warnings


def deadline_status(deadline, checked_at):
    if deadline in ("unknown", "ambiguous"):
        return "unknown"
    return "open" if date.fromisoformat(deadline) >= date.fromisoformat(checked_at) else "closed"
