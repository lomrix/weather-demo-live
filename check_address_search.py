"""Offline checks with synthetic Kartverket responses; no live requests."""
import copy
import io
import json
import threading
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
from unittest.mock import patch

from harness.address_search import AddressSearch, LIMIT, MAX_BYTES, NoRedirect, source_url
import hamar_workspace


def response(name="Seminargata 13", municipality="3403", lat=60.795, lon=11.072):
    return {"metadata": {"totaltAntallTreff": 1}, "adresser": [{
        "adressetekstutenadressetilleggsnavn": name, "adressenavn": "Seminargata",
        "kommunenummer": municipality, "postnummer": "2317", "poststed": "HAMAR",
        "representasjonspunkt": {"epsg":"EPSG:4258", "lat":lat, "lon":lon},
        "owner": "MUST NOT REACH THE CLIENT", "bruksenhetsnummer": ["H0101"]}]}


class FakeSource:
    def __init__(self, data=None, error=None, raw=None):
        self.data = data if data is not None else response()
        self.error, self.raw, self.calls = error, raw, []

    def __call__(self, request, timeout):
        self.calls.append((request.full_url, timeout))
        if self.error:
            raise self.error
        return io.BytesIO(self.raw if self.raw is not None else json.dumps(self.data).encode())


class AddressSearchTests(unittest.TestCase):
    def test_fixed_source_scope_and_exact_house_number(self):
        params=parse_qs(urlsplit(source_url("Seminargata 13B")).query,keep_blank_values=True)
        self.assertEqual(params["kommunenummer"],["3403"])
        self.assertEqual(params["nummer"],["13"])
        self.assertEqual(params["bokstav"],["B"])
        self.assertEqual(params["sok"],["Seminargata*"])
        self.assertEqual(params["treffPerSide"],[str(LIMIT)])
        self.assertNotIn("bokstav",parse_qs(urlsplit(source_url("Seminargata 1")).query))
        self.assertNotIn("bruksenhetsnummer",params["filtrer"][0])
        self.assertEqual(urlsplit(source_url("https://elsewhere.invalid")).netloc,"api.kartverket.no")

    def test_projected_results_preserve_provenance_not_extra_fields(self):
        fake=FakeSource()
        result=AddressSearch(fake).search("Seminargata")
        self.assertEqual(result["status"],"available")
        item=result["matches"][0]
        self.assertEqual(item["name"],"Seminargata 13")
        self.assertEqual(item["coordinates"],[60.795,11.072])
        self.assertEqual(item["source"]["attribution"],"© Kartverket")
        self.assertEqual(len(item["source"]["sha256"]),64)
        self.assertNotIn("owner",json.dumps(result))
        self.assertNotIn("bruksenhetsnummer",json.dumps(result))
        self.assertEqual(len(fake.calls),1)
        self.assertEqual(fake.calls[0][1],5)

    def test_no_match_is_distinct_from_source_outage(self):
        empty=AddressSearch(FakeSource({"metadata":{"totaltAntallTreff":0},"adresser":[]})).search("Unknownstreet")
        unavailable=AddressSearch(FakeSource(error=URLError("offline"))).search("Seminargata")
        self.assertEqual(empty["status"],"available")
        self.assertEqual(empty["matches"],[])
        self.assertEqual(unavailable["status"],"unavailable")
        self.assertIsNone(unavailable["total"])

    def test_invalid_short_or_numeric_queries_never_request(self):
        fake=FakeSource(); search=AddressSearch(fake)
        for query in ("", "ab", "1234", "x"*81, "Semi\nnergata", None):
            with self.subTest(query=query), self.assertRaises(ValueError):
                search.search(query)
        self.assertFalse(fake.calls)

    def test_wrong_municipality_and_bad_coordinates_fail_closed(self):
        for data in (response(municipality="0301"), response(lat=True), response(lon=99), response(lat=float("nan")), {"adresser":[None]}, {"adresser":[]}):
            with self.subTest(data=data):
                self.assertEqual(AddressSearch(FakeSource(data)).search("Seminargata")["status"],"unavailable")

    def test_size_schema_and_redirect_limits(self):
        for fake in (FakeSource(raw=b"x"*(MAX_BYTES+1)), FakeSource(raw=b"not-json"),FakeSource({"adresser":[{}]*(LIMIT+1)})):
            self.assertEqual(AddressSearch(fake).search("Seminargata")["status"],"unavailable")
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None,None,None,None,None,None)

    def test_cache_ttl_is_bounded_and_returns_independent_values(self):
        now=[10]; fake=FakeSource(); search=AddressSearch(fake,clock=lambda:now[0])
        a=search.search("Seminargata");a["matches"].clear()
        self.assertEqual(len(search.search("seminargata")["matches"]),1)
        self.assertEqual(len(fake.calls),1)
        now[0]+=601; search.search("Seminargata")
        self.assertEqual(len(fake.calls),2)
        for i in range(150):
            now[0]+=2;search.search("Street "+str(i))
        self.assertLessEqual(len(search.cache),128)

    def test_rate_and_concurrency_limits_do_not_start_requests(self):
        fake=FakeSource(); search=AddressSearch(fake,clock=lambda:5)
        search.calls.extend([5]*60)
        self.assertEqual(search.search("Seminargata")["status"],"unavailable")
        self.assertEqual(fake.calls,[])
        search.calls.clear();search.slots.acquire();search.slots.acquire()
        self.assertEqual(search.search("Seminargata")["status"],"unavailable")
        self.assertEqual(fake.calls,[])
        search.slots.release();search.slots.release()

    def test_truncation_duplicates_and_stable_ids(self):
        data=response();data["metadata"]["totaltAntallTreff"]=44
        data["adresser"].append(copy.deepcopy(data["adresser"][0]))
        fake=FakeSource(data);a=AddressSearch(fake).search("Seminargata")
        b=AddressSearch(fake).search("Seminargata")
        self.assertTrue(a["truncated"])
        self.assertEqual(len(a["matches"]),1)
        self.assertEqual(a["matches"][0]["id"],b["matches"][0]["id"])


class AddressHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake=FakeSource()
        cls.server=hamar_workspace.WorkspaceServer(0,address_opener=cls.fake)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()

    def test_address_endpoint_and_validation(self):
        base="http://127.0.0.1:"+str(self.server.server_port)
        with urlopen(base+"/api/addresses?q=Seminargata") as source:
            self.assertEqual(json.load(source)["matches"][0]["kind"],"address")
        with self.assertRaises(HTTPError) as result:
            urlopen(base+"/api/addresses?q=ab")
        self.assertEqual(result.exception.code,400)

    def test_console_logs_omit_query(self):
        handler=object.__new__(hamar_workspace.Handler)
        handler.command="GET";handler.path="/api/addresses?q=private-search"
        with patch("sys.stderr",new_callable=io.StringIO) as output:
            handler.log_message("ignored")
        self.assertEqual(output.getvalue(),"GET /api/addresses\n")


if __name__ == "__main__":
    unittest.main()
