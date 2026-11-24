"""Offline checks for reviewed municipal notices and synthetic revisions."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import hamar_workspace
from harness.city_notices import notice_feed


ROOT = Path(__file__).resolve().parent
FEED = Path("fixtures/notices/hamar-area.json")


class CityNoticeTests(unittest.TestCase):
    def test_municipal_evidence_is_available_without_journeys(self):
        handler = hamar_workspace.Handler.__new__(hamar_workspace.Handler)
        handler.path = "/api/notifications"
        handler.headers = {"Host": "127.0.0.1:8765"}
        handler.server = SimpleNamespace(root=ROOT, allowed_hosts={"127.0.0.1:8765"})
        handler._json = Mock()
        handler.do_GET()
        status, data = handler._json.call_args.args
        self.assertEqual(status, 200)
        real = [notice for notice in data["notices"] if not notice["synthetic"]]
        self.assertEqual(len(real), 4)
        self.assertTrue(all(record["evidence"] and record["last_checked"] for record in real))
        self.assertTrue(all(record["source_url"].startswith("https://www.hamar.kommune.no/")
                            and not record["modeled"] for record in real))

        handler.server.root = ROOT / "missing-fixture-root"
        handler.do_GET()
        status, data = handler._json.call_args.args
        self.assertEqual(status, 503)
        self.assertNotIn("notices", data)

    def test_source_summaries_are_distinct_from_quotations(self):
        notices = {item["id"]: item for item in notice_feed(ROOT, date(2026, 11, 24))}
        self.assertEqual(notices["gasbuvegen-through-traffic"]["evidence_kind"], "summary")
        self.assertEqual(notices["skappelsgate-waterworks"]["evidence_kind"], "summary")
        self.assertEqual(notices["koigen-footpath"]["evidence_kind"], "quote")
        self.assertEqual(notices["demo-extension"]["previous_period"]["evidence_kind"], "note")

    def test_scheduled_end_never_confirms_reopening(self):
        before = {item["id"]: item for item in notice_feed(ROOT, date(2026, 9, 13))}
        after = {item["id"]: item for item in notice_feed(ROOT, date(2026, 11, 24))}
        road = "gasbuvegen-through-traffic"
        self.assertFalse(before[road]["reopening_unconfirmed"])
        self.assertTrue(after[road]["reopening_unconfirmed"])
        self.assertEqual(after[road]["status"], "closure_announced")
        self.assertNotEqual(after[road]["event_id"], before[road]["event_id"])
        self.assertFalse(after["koigen-footpath"]["reopening_unconfirmed"])
        self.assertEqual(after["koigen-works"]["status"], "works_started")
        self.assertEqual(after["demo-reopened"]["status"], "reopened")
        self.assertTrue(after["demo-reopened"]["synthetic"])

    def test_synthetic_revisions_detect_new_active_and_extended_notices(self):
        records = json.loads((ROOT / FEED).read_text(encoding="utf-8"))
        works = next(record for record in records if record["id"] == "demo-extension")
        upcoming = next(record for record in records if record["id"] == "demo-upcoming")
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            path = root / FEED
            path.parent.mkdir(parents=True)

            def load(dataset):
                path.write_text(json.dumps(dataset), encoding="utf-8")
                return notice_feed(root, date(2026, 11, 24))

            self.assertEqual(load([]), [])
            self.assertEqual(load([upcoming])[0]["status"], "works_upcoming")
            announced, active = works["revisions"]
            first, = load([{**works, "revisions": [announced]}])
            self.assertEqual(first["status"], "closure_announced")
            latest, = load([works])
            self.assertEqual(latest["id"], first["id"])
            self.assertNotEqual(latest["event_id"], first["event_id"])
            self.assertEqual(latest["status"], "closure_active")
            self.assertEqual(latest["previous_period"]["end_date"], "2026-11-25")
            refreshed, = load([{**works, "revisions": [
                announced, active, {**active, "last_checked": "2026-11-25T12:00:00+01:00"},
            ]}])
            self.assertEqual(latest["event_id"], refreshed["event_id"])
            self.assertNotEqual(latest["last_checked"], refreshed["last_checked"])
