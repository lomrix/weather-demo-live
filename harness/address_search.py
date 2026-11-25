"""Bounded, municipality-scoped lookup of public address points from Kartverket.

Only public street/house-number and geographic fields are requested. No owner,
resident, apartment, property-title or contact data is requested or retained.
Searches are held only in a short-lived, bounded memory cache, never on disk.
"""
import copy
import hashlib
import json
import math
import re
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://api.kartverket.no/adresser/v1/sok"
MUNICIPALITY = "3403"
LIMIT = 20
TIMEOUT = 5
MAX_BYTES = 256 * 1024
FIELDS = ("adressenavn", "adressetekstutenadressetilleggsnavn", "nummer", "bokstav",
          "postnummer", "poststed", "kommunenummer", "representasjonspunkt")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ValueError("Address-source redirects are not allowed")


def clean_query(value):
    if not isinstance(value, str) or len(value) > 80 or any(ord(c) < 32 for c in value):
        raise ValueError("Use an address search of at most 80 characters")
    text = " ".join(value.split())
    if len(text) < 3 or not any(c.isalpha() for c in text):
        raise ValueError("Type at least three characters of a street name")
    return text


def source_url(query):
    text = clean_query(query)
    params = {"kommunenummer": MUNICIPALITY, "treffPerSide": LIMIT,
              "side": 0, "utkoordsys": 4258,
              "filtrer": "metadata," + ",".join("adresser." + key for key in FIELDS)}
    # House numbers are exact: 1 must not silently become 10 or 100.
    house = re.fullmatch(r"(.+?\D)\s*(\d+)\s*([a-zA-Z]?)", text)
    if house:
        params["sok"] = house[1].strip().replace("*", "") + "*"
        params["nummer"] = int(house[2])
        if house[3]:
            params["bokstav"] = house[3].upper()
    else:
        params["sok"] = text.replace("*", "") + "*"
    return ENDPOINT + "?" + urlencode(params)


def project_response(data, url, checked, digest):
    if not isinstance(data, dict) or not isinstance(data.get("adresser"), list):
        raise ValueError("Invalid address response")
    if len(data["adresser"]) > LIMIT:
        raise ValueError("Address source exceeded its result limit")
    source = {"provider": "Kartverket", "attribution": "© Kartverket",
              "licence_url": "https://creativecommons.org/licenses/by/4.0/",
              "source_url": url, "retrieved_at_utc": checked, "sha256": digest}
    matches, seen = [], set()
    for row in data["adresser"]:
        if not isinstance(row, dict) or row.get("kommunenummer") != MUNICIPALITY:
            raise ValueError("Address source returned a different municipality")
        name = row.get("adressetekstutenadressetilleggsnavn")
        street = row.get("adressenavn")
        point = row.get("representasjonspunkt", {})
        if not isinstance(point, dict):
            raise ValueError("Invalid address coordinate object")
        lat, lon = point.get("lat"), point.get("lon")
        if (not isinstance(name, str) or not name or len(name) > 180
                or not isinstance(street, str) or not street
                or point.get("epsg") != "EPSG:4258"
                or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in (lat, lon))
                or not (59 < lat < 63 and 9 < lon < 13)):
            raise ValueError("Invalid Hamar address point")
        stable = hashlib.sha256(f"{MUNICIPALITY}|{name}|{lat}|{lon}".encode()).hexdigest()[:24]
        if stable in seen:
            continue
        seen.add(stable)
        matches.append({"id": "kartverket-" + stable, "name": name,
                        "kind": "address", "coordinates": [lat, lon],
                        "street": street, "postal_code": row.get("postnummer", ""),
                        "postal_place": row.get("poststed", ""),
                        "source_id": "kartverket-addresses", "source": source})
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Invalid address metadata")
    total = metadata.get("totaltAntallTreff")
    if not isinstance(total, int) or isinstance(total, bool) or total < len(matches):
        raise ValueError("Invalid address result count")
    matches.sort(key=lambda item: (item["street"].casefold(), int(re.search(r"\d+", item["name"])[0])
                                  if re.search(r"\d+", item["name"]) else 0, item["name"]))
    return {"status": "available", "matches": matches, "total": total,
            "truncated": total > len(matches), "source": source}


class AddressSearch:
    def __init__(self, opener=None, clock=time.monotonic):
        self.opener = opener or build_opener(NoRedirect()).open
        self.clock = clock
        self.cache = OrderedDict()
        self.calls = deque()
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)

    def search(self, query):
        query = clean_query(query)
        key = query.casefold()
        now = self.clock()
        with self.lock:
            cached = self.cache.get(key)
            if cached and now - cached[0] < 600:
                self.cache.move_to_end(key)
                return copy.deepcopy(cached[1])
            while self.calls and now - self.calls[0] >= 60:
                self.calls.popleft()
            if len(self.calls) >= 60:
                return self.unavailable("Address search is busy. Please try again shortly.")
            if not self.slots.acquire(blocking=False):
                return self.unavailable("Address search is busy. Please try again shortly.")
            self.calls.append(now)
        try:
            url = source_url(query)
            request = Request(url, headers={"User-Agent": "HamarAccessLab/1.0", "Accept": "application/json"})
            with self.opener(request, timeout=TIMEOUT) as response:
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Address response exceeded its size limit")
            result = project_response(json.loads(raw), url, datetime.now(timezone.utc).isoformat(),
                                      hashlib.sha256(raw).hexdigest())
            with self.lock:
                self.cache[key] = (self.clock(), copy.deepcopy(result))
                self.cache.move_to_end(key)
                while len(self.cache) > 128:
                    self.cache.popitem(last=False)
            return result
        except (OSError, ValueError, TypeError, KeyError):
            return self.unavailable("Address lookup is unavailable. Saved places and map selection still work.")
        finally:
            self.slots.release()

    @staticmethod
    def unavailable(message):
        return {"status": "unavailable", "matches": [], "total": None,
                "truncated": False, "message": message}
