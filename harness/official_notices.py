"""Explicit, bounded checks of the Hamar municipality traffic notice index."""

import hashlib
import json
import re
import threading
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from http.client import HTTPException
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4


ORIGIN = "https://www.hamar.kommune.no"
INDEX = ORIGIN + "/veger-og-gater/trafikkmeldinger/"
ARTICLE = re.compile(r"/(?:veger-og-gater/trafikkmeldinger|nyhetsarkiv|utviklingsomrader)/[a-z0-9-]+/?")
ARTICLE_LIMIT = 5
MAX_BYTES = 1024 * 1024
TIMEOUT = 4
DATA_DIR = Path("out/official-notices")
FEED = Path("fixtures/notices/hamar-area.json")
BLOCK = {"article", "div", "section", "p", "li", "h1", "h2", "h3", "h4", "br", "td", "th"}
EXCLUDED = {"script", "style", "nav", "aside", "footer", "form"}
CONTACT_MARKER = re.compile(r"\b(?:contact|kontakt|byline|author|forfatter)\b", re.I)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def article_url(link, base=INDEX):
    try:
        parts = urlsplit(urljoin(base, link))
    except ValueError:
        return None
    if (parts.scheme == "https" and parts.netloc == urlsplit(ORIGIN).netloc
            and ARTICLE.fullmatch(parts.path)):
        return ORIGIN + parts.path.rstrip("/")
    return None


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class MainContent(HTMLParser):
    """Collect main-content text and links, omitting site chrome and contact sections."""

    def __init__(self, html):
        super().__init__()
        self.in_head = False
        self.canonical_links = []
        self.in_main = False
        self.skip = []
        self.parts = []
        self.links = []
        self.in_title = False
        self.title = []
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attributes):
        if tag == "head":
            self.in_head = True
        if tag == "main":
            self.in_main = True
        attrs = dict(attributes)
        if (self.in_head and tag == "link" and attrs.get("href")
                and "canonical" in (attrs.get("rel") or "").lower().split()):
            self.canonical_links.append(attrs["href"])
        marker = f"{attrs.get('class', '')} {attrs.get('id', '')}"
        if self.in_main and (tag in EXCLUDED or (tag in BLOCK and CONTACT_MARKER.search(marker))):
            self.skip.append(tag)
        elif self.in_main and self.skip and tag == self.skip[-1]:
            self.skip.append(tag)
        if self.in_main and not self.skip and tag in BLOCK:
            self.parts.append(" ")
        if self.in_main and not self.skip and tag == "a":
            href = attrs.get("href")
            if href:
                self.links.append(href)
        if self.in_main and not self.skip and tag == "h1":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        if self.skip and tag == self.skip[-1]:
            self.skip.pop()
        if tag == "main":
            self.in_main = False
        if tag == "h1":
            self.in_title = False
        if self.in_main and not self.skip and tag in BLOCK:
            self.parts.append(" ")

    def handle_data(self, data):
        if self.in_main and not self.skip:
            self.parts.append(data)
            if self.in_title:
                self.title.append(data)

    @property
    def text(self):
        text = " ".join("".join(self.parts).split())
        text = re.split(r"Fant du ikke det du lette etter\?|Ta kontakt med oss for hjelp", text, maxsplit=1)[0]
        # Omit direct contact details that may appear in article copy.
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[…]", text)
        return re.sub(r"(?:\+47\s*)?\b\d{2} \d{2} \d{2} \d{2}\b", "[…]", text).strip()


def state_at(root):
    try:
        return json.loads((root / DATA_DIR / "state.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"observed": {}, "pending": {}, "accepted": {}}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        name = Path(temp.name)
        try:
            json.dump(value, temp, ensure_ascii=False)
            temp.close()
            name.replace(path)
        finally:
            name.unlink(missing_ok=True)


class OfficialNotices:
    def __init__(self, root, opener=None):
        self.root = Path(root)
        self.open = opener or build_opener(ProxyHandler({}), NoRedirects()).open
        self.lock = threading.Lock()

    def fetch(self, url):
        if url != INDEX and article_url(url) != url:
            raise ValueError("Unapproved official notice URL")
        deadline = time.monotonic() + TIMEOUT
        request = Request(url, headers={"Accept": "text/html", "User-Agent": "HamarAccessLab/1.0"})
        with self.open(request, timeout=TIMEOUT) as response:
            if (response.status != 200 or response.geturl() != url
                    or response.headers.get_content_type() != "text/html"):
                raise ValueError("Unexpected official notice response")
            body = bytearray()
            while len(body) <= MAX_BYTES:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Official notice read deadline")
                chunk = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise ValueError("Official notice response exceeds size limit")
            html = body.decode(response.headers.get_content_charset("utf-8"))
        content = MainContent(html)
        text = content.text
        if not text:
            raise ValueError("Official notice has no main content")
        canonical = {article_url(link, base=url) for link in content.canonical_links} - {None}
        source_url = canonical.pop() if url != INDEX and len(canonical) == 1 else url
        return content, {
            "url": source_url, "retrieved_url": url, "retrieved_at": datetime.now(UTC).isoformat(),
            "response_sha256": digest(body), "text_sha256": digest(text.encode()),
            "text": text, "title": " ".join("".join(content.title).split())[:160]
            or urlsplit(url).path.rsplit("/", 1)[-1] or "Trafikkmeldinger",
        }

    def review_queue(self):
        state = state_at(self.root)
        return {"pending": list(state["pending"].values()), "last_check": state.get("last_check")}

    def check(self, payload):
        if payload != {}:
            raise ValueError("Official source check accepts no URLs or options")
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError("Official source check or review is in progress")
        try:
            return self._check()
        finally:
            self.lock.release()

    def _check(self):
        state = state_at(self.root)
        records = json.loads((self.root / FEED).read_text(encoding="utf-8"))
        seeds = {article_url(record["source_url"]) for record in records if not record["synthetic"]}
        seeds.discard(None)
        report = {"checked_at": datetime.now(UTC).isoformat(), "results": [], "limited": False}
        snapshots = []

        def fetch(url):
            try:
                content, snapshot = self.fetch(url)
            except (OSError, ValueError, LookupError, HTTPException):
                report["results"].append({"url": url, "status": "unavailable"})
                return None, None
            snapshots.append(snapshot)
            return content, snapshot

        index, _ = fetch(INDEX)
        if index is not None:
            links = list(dict.fromkeys(url for link in index.links if (url := article_url(link))))
            report["results"].append({"url": INDEX, "status": "checked" if links else "no_links"})
            report["limited"] = len(links) > ARTICLE_LIMIT
            seen = set()
            for retrieved_url in links[:ARTICLE_LIMIT]:
                _, snapshot = fetch(retrieved_url)
                if snapshot is None:
                    continue
                url = snapshot["url"]
                if url in seen:
                    continue
                seen.add(url)
                previous = state["observed"].get(url)
                same = previous and previous["text_sha256"] == snapshot["text_sha256"]
                status = "unchanged" if same else "changed" if previous else "baseline" if url in seeds else "new"
                report["results"].append({"url": url, "status": status})
                if not same:
                    accepted = state["accepted"].get(url)
                    if accepted and accepted["snapshot"]["text_sha256"] == snapshot["text_sha256"]:
                        state["pending"].pop(url, None)
                    else:
                        state["pending"][url] = {
                            "status": status, "snapshot": snapshot,
                            "previous": accepted["snapshot"] if accepted else previous,
                        }
                state["observed"][url] = snapshot
            for url in sorted((seeds | state["observed"].keys()) - seen - set(links)):
                report["results"].append({"url": url, "status": "unlisted"})
        state["last_check"] = report
        directory = self.root / DATA_DIR
        write_json(directory / "checks" / f"{uuid4().hex}.json",
                   {"report": report, "snapshots": snapshots})
        write_json(directory / "state.json", state)
        return {"pending": list(state["pending"].values()), "last_check": report}

    def accept(self, payload):
        fields = {"url", "text_sha256", "quote", "summary"}
        if (not isinstance(payload, dict) or payload.keys() != fields
                or any(not isinstance(value, str) for value in payload.values())):
            raise ValueError("Send the pending source, its hash, an exact quote and a summary")
        url = payload["url"]
        quote = payload["quote"].strip()
        summary = payload["summary"].strip()
        if article_url(url) != url or not 12 <= len(quote) <= 500 or len(summary) > 400:
            raise ValueError("Invalid notice review fields")
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError("Official source check or review is in progress")
        try:
            state = state_at(self.root)
            pending = state["pending"].get(url)
            if not pending or pending["snapshot"]["text_sha256"] != payload["text_sha256"]:
                raise BlockingIOError("This source is no longer pending at that revision")
            snapshot = pending["snapshot"]
            if "[…]" in quote or quote not in snapshot["text"]:
                raise ValueError("The quotation must occur verbatim in the saved source text")
            state["accepted"][url] = {
                "snapshot": snapshot, "quote": quote, "summary": summary,
                "accepted_at": datetime.now(UTC).isoformat(),
            }
            del state["pending"][url]
            directory = self.root / DATA_DIR
            write_json(directory / "reviews" / f"{uuid4().hex}.json", state["accepted"][url])
            write_json(directory / "state.json", state)
            return {"pending": list(state["pending"].values()), "last_check": state.get("last_check")}
        finally:
            self.lock.release()
