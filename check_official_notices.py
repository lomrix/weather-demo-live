"""Offline municipal-page fixtures and injected transport failures."""

import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

from harness.city_notices import notice_feed
from harness.official_notices import DATA_DIR, FEED, INDEX, MAX_BYTES, OfficialNotices, article_url


ROOT = Path(__file__).resolve().parent
OLD = "https://www.hamar.kommune.no/nyhetsarkiv/sjoledning-skal-pa-plass-mellom-koigen-og-tjuvholmen"
NEW = INDEX + "synthetic-notice"
ALIAS = INDEX + OLD.rsplit("/", 1)[-1]
TEXT = "The works are planned for December 1–3. Closure dates are unknown."
UPDATED = TEXT.replace("1–3", "1–6")


def main(body, canonical=None):
    head = f'<head><link rel="canonical" href="{canonical}"></head>' if canonical else ""
    return f"<html>{head}<nav>Excluded navigation</nav><main>{body}</main></html>".encode()


class Response(io.BytesIO):
    status = 200

    def __init__(self, url, body):
        super().__init__(body)
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def geturl(self):
        return self.url


class OfficialNoticeTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        (self.root / FEED).parent.mkdir(parents=True)
        (self.root / FEED).write_bytes((ROOT / FEED).read_bytes())
        self.calls = []
        self.pages = {
            INDEX: main(f'<a href="{OLD}">Existing</a><a href="{NEW}">New</a>'
                        '<a href="https://example.com/nyhetsarkiv/lookalike">External</a>'),
            OLD: main(f"<h1>Koigen</h1><p>{TEXT}</p>"),
            NEW: main(f"<h1>New notice</h1><p>{TEXT}</p>"),
        }
        self.service = OfficialNotices(self.root, self.open)

    def open(self, request, timeout):
        url = request.full_url
        self.calls.append((url, timeout))
        body = self.pages.get(url)
        if body is None:
            raise HTTPError(url, 404, "Fixture unavailable", {}, None)
        return Response(url, body)

    def accept(self, item, quote=TEXT):
        snapshot = item["snapshot"]
        return self.service.accept({
            "url": snapshot["url"], "text_sha256": snapshot["text_sha256"],
            "quote": quote, "summary": "Reviewer notes the stated project schedule.",
        })

    def test_new_source_and_first_snapshot_are_pending_until_acceptance(self):
        before = notice_feed(self.root)
        result = self.service.check({})
        self.assertEqual([item["status"] for item in result["pending"]], ["baseline", "new"])
        self.assertEqual(notice_feed(self.root), before)
        snapshot = result["pending"][1]["snapshot"]
        self.assertEqual(snapshot["url"], NEW)
        self.assertIn(TEXT, snapshot["text"])
        self.assertNotIn("Excluded navigation", snapshot["text"])
        self.assertEqual(len(snapshot["response_sha256"]), 64)
        self.assertIn("+00:00", snapshot["retrieved_at"])
        with self.assertRaises(ValueError):
            self.accept(result["pending"][1], "A paraphrase of the official statement.")
        self.accept(result["pending"][1])
        reviewed = next(item for item in notice_feed(self.root) if item["source_url"] == NEW)
        self.assertEqual(reviewed["evidence"], TEXT)
        self.assertEqual(reviewed["evidence_kind"], "quote")
        self.assertNotEqual(reviewed["summary"], reviewed["evidence"])
        self.assertNotIn("start_date", reviewed)
        self.assertNotIn("end_date", reviewed)
        self.assertEqual(reviewed["status"], "notice_reviewed")

    def test_seed_discovered_through_alias_is_a_baseline_and_reviewed_once(self):
        self.pages[INDEX] = main(f'<a href="{ALIAS}">Koigen</a>')
        self.pages[ALIAS] = main(f"<h1>Koigen</h1><p>{TEXT}</p>", "/nyhetsarkiv/" + OLD.rsplit("/", 1)[-1])
        result = self.service.check({})
        item, = result["pending"]
        self.assertEqual(item["status"], "baseline")
        self.assertEqual(item["snapshot"]["url"], OLD)
        self.assertEqual(item["snapshot"]["retrieved_url"], ALIAS)
        self.assertNotIn({"url": OLD, "status": "unlisted"}, result["last_check"]["results"])
        self.accept(item)
        reviewed, = [card for card in notice_feed(self.root) if card["source_url"] in {OLD, ALIAS}]
        self.assertEqual(reviewed["source_url"], OLD)
        with self.assertRaises(BlockingIOError):
            self.accept(item)
        self.assertEqual(self.service.check({})["pending"], [])

    def test_aliases_share_one_observation_and_review_but_archive_each_fetch(self):
        other_alias = INDEX + "second-koigen-alias"
        self.pages[INDEX] = main("".join(f'<a href="{url}">Koigen</a>' for url in (ALIAS, other_alias, OLD)))
        for url in (ALIAS, other_alias):
            self.pages[url] = main(f"<h1>Koigen</h1><p>{TEXT}</p>", OLD)
        result = self.service.check({})
        item, = result["pending"]
        self.assertEqual(item["snapshot"]["url"], OLD)
        self.assertEqual([entry for entry in result["last_check"]["results"] if entry["url"] == OLD],
                         [{"url": OLD, "status": "baseline"}])
        archive, = (self.root / DATA_DIR / "checks").glob("*.json")
        snapshots = json.loads(archive.read_text(encoding="utf-8"))["snapshots"]
        self.assertEqual([s["retrieved_url"] for s in snapshots if s["url"] == OLD], [ALIAS, other_alias, OLD])
        self.accept(item)
        self.pages[INDEX] = main(f'<a href="{other_alias}">Koigen</a>')
        result = self.service.check({})
        self.assertEqual(result["pending"], [])
        self.assertIn({"url": OLD, "status": "unchanged"}, result["last_check"]["results"])
        self.assertEqual(sum(card["source_url"] == OLD for card in notice_feed(self.root)), 1)

    def test_unapproved_canonical_cannot_change_identity_or_trigger_a_fetch(self):
        self.pages[INDEX] = main(f'<a href="{NEW}">Notice</a>')
        for canonical in ("https://example.com/nyhetsarkiv/notice",
                          "https://www.hamar.kommune.no/other-section/notice"):
            with self.subTest(canonical=canonical):
                self.calls.clear()
                self.pages[NEW] = main(f"<h1>Notice</h1><p>{TEXT}</p>", canonical)
                item, = self.service.check({})["pending"]
                self.assertEqual(item["snapshot"]["url"], NEW)
                self.assertEqual([url for url, _ in self.calls], [INDEX, NEW])

    def test_changed_dates_stay_pending_unchanged_checks_preserve_ids(self):
        first = self.service.check({})["pending"][0]
        self.accept(first)
        reviewed = notice_feed(self.root)
        unchanged = self.service.check({})
        self.assertEqual(unchanged["last_check"]["results"][1]["status"], "unchanged")
        self.assertEqual(notice_feed(self.root), reviewed)
        self.pages[OLD] = main(f"<h1>Koigen</h1><p>{UPDATED}</p>")
        changed = self.service.check({})
        item = next(item for item in changed["pending"] if item["snapshot"]["url"] == OLD)
        self.assertEqual(item["status"], "changed")
        self.assertIn(TEXT, item["previous"]["text"])
        self.assertIn(UPDATED, item["snapshot"]["text"])
        self.assertEqual(notice_feed(self.root), reviewed)
        with self.assertRaises(BlockingIOError):
            self.accept(first)
        self.accept(item, UPDATED)
        new = next(notice for notice in notice_feed(self.root) if notice["source_url"] == OLD)
        self.assertNotEqual(new["event_id"], next(n for n in reviewed if n["source_url"] == OLD)["event_id"])
        self.assertFalse(new["reopening_unconfirmed"])
        self.assertEqual(len(list((self.root / DATA_DIR / "checks").glob("*.json"))), 3)

    def test_unavailable_index_and_article_preserve_reviewed_evidence(self):
        self.accept(self.service.check({})["pending"][0])
        reviewed = notice_feed(self.root)
        del self.pages[OLD]
        result = self.service.check({})
        self.assertIn({"url": OLD, "status": "unavailable"}, result["last_check"]["results"])
        self.assertEqual(notice_feed(self.root), reviewed)
        self.pages[INDEX] = main("No links")
        result = self.service.check({})
        self.assertIn({"url": OLD, "status": "unlisted"}, result["last_check"]["results"])
        self.assertEqual(notice_feed(self.root), reviewed)
        del self.pages[INDEX]
        pending = result["pending"]
        result = self.service.check({})
        self.assertEqual(result["pending"], pending)
        self.assertEqual(result["last_check"]["results"], [{"url": INDEX, "status": "unavailable"}])
        self.assertEqual(notice_feed(self.root), reviewed)

    def test_url_allowlist_rejects_external_and_unapproved_paths_before_requests(self):
        urls = ["https://example.com/nyhetsarkiv/test", "http://www.hamar.kommune.no/nyhetsarkiv/test",
                "https://www.hamar.kommune.no@other.example/nyhetsarkiv/test",
                "https://www.hamar.kommune.no/other-section/test",
                "https://www.hamar.kommune.no/nyhetsarkiv/%2e%2e"]
        for url in urls:
            with self.subTest(url=url):
                self.assertIsNone(article_url(url))
                with self.assertRaises(ValueError):
                    self.service.fetch(url)
        with self.assertRaises(ValueError):
            self.service.check({"url": NEW})
        self.assertFalse(self.calls)
        self.service.check({})
        self.assertEqual([url for url, _ in self.calls], [INDEX, OLD, NEW])

    def test_size_and_request_count_are_bounded(self):
        links = [INDEX + f"synthetic-{index}" for index in range(9)]
        self.pages[INDEX] = main("".join(f'<a href="{url}">Article</a>' for url in links))
        self.pages[links[0]] = b"x" * (MAX_BYTES + 1)
        result = self.service.check({})
        self.assertTrue(result["last_check"]["limited"])
        self.assertEqual([url for url, _ in self.calls], [INDEX, *links[:5]])
        self.assertTrue(all(timeout == 4 for _, timeout in self.calls))
        self.assertIn({"url": links[0], "status": "unavailable"}, result["last_check"]["results"])

    def test_redirected_or_timed_out_article_is_unavailable(self):
        def failed_open(request, timeout):
            if request.full_url == NEW:
                raise TimeoutError("Synthetic timeout")
            if request.full_url == OLD:
                return Response("https://example.com/redirected", self.pages[OLD])
            return self.open(request, timeout)

        result = OfficialNotices(self.root, failed_open).check({})
        self.assertEqual(result["pending"], [])
        self.assertEqual([item for item in result["last_check"]["results"] if item["status"] == "unavailable"], [
            {"url": OLD, "status": "unavailable"}, {"url": NEW, "status": "unavailable"},
        ])
