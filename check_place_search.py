"""Focused checks for Hamar place search and browser-local journeys."""

import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))

import hamar_workspace
from build_place_index import build
from workspace_service import Workspace


class FakeOpener:
    def __call__(self, *_args, **_kwargs):
        raise AssertionError("Place search must not call a network opener")


class PlaceIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = Workspace(ROOT, FakeOpener())
        cls.index = cls.workspace.place_index

    def test_checked_index_is_reproducible(self):
        checked = json.loads(
            (ROOT / "fixtures" / "places" / "hamar-place-index.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(checked, build(ROOT))
        self.assertGreater(len(checked["places"]), 50)
        self.assertTrue(checked["generated_from_saved_data_only"])
        self.assertTrue(all(place["source"]["sha256"] for place in checked["places"]))

    def test_search_is_bounded_sourced_and_has_no_match(self):
        result = self.workspace.search_places("Stortorget")
        self.assertTrue(result["matches"])
        self.assertTrue(all(place["kind"] == "bus_stop" for place in result["matches"]))
        self.assertTrue(all(place["source"]["file"].endswith(".json") for place in result["matches"]))
        self.assertEqual(
            result["matches"][0]["source"]["provider"],
            "Entur AS",
        )
        self.assertEqual(self.workspace.search_places("no-such-local-place")["matches"], [])
        broad = self.workspace.search_places("a")
        self.assertLessEqual(len(broad["matches"]), 20)
        self.assertTrue(broad["truncated"])
        with self.assertRaises(ValueError):
            self.workspace.search_places("x" * 81)
        with self.assertRaises(ValueError):
            self.workspace.search_places(" ")

    def test_named_place_preserves_scenario_map_provenance(self):
        result = self.workspace.search_places("Ringgata crossing")
        self.assertTrue(result["matches"])
        for place in result["matches"]:
            self.assertEqual(place["kind"], "named_place")
            self.assertIn("scenario", place["source"]["file"])
            self.assertTrue(place["source"]["map_sha256"])
            self.assertIn("OpenStreetMap contributors", place["source"]["attribution"])

    def test_selected_search_coordinate_uses_existing_resolution(self):
        place = self.workspace.search_places("Stortorget")["matches"][0]
        lat, lon = place["coordinates"]
        other = self.workspace.search_places("CC Hamar")["matches"][0]
        resolved = self.workspace.resolve_journey({
            "case_id": "hamar-urban",
            "custom_journey": {
                "origin": {"lat": lat, "lon": lon},
                "destination": {
                    "lat": other["coordinates"][0],
                    "lon": other["coordinates"][1],
                },
            },
        })
        self.assertEqual(resolved["status"], "ready")
        self.assertIsInstance(resolved["baseline_metres"], int)

    def test_outside_coverage_and_no_connection_are_distinct(self):
        outside = self.workspace.search_places("Sanderud sykehus")["matches"][0]
        normal = self.workspace.search_places("Stortorget")["matches"][0]
        resolved = self.workspace.resolve_journey({
            "case_id": "hamar-urban",
            "custom_journey": {
                "origin": {
                    "lat": outside["coordinates"][0],
                    "lon": outside["coordinates"][1],
                },
                "destination": {
                    "lat": normal["coordinates"][0],
                    "lon": normal["coordinates"][1],
                },
            },
        })
        self.assertEqual(resolved["status"], "outside_coverage")
        self.assertEqual(resolved["origin"]["reason"], "outside_extract")

        case = self.workspace.get_case("hamar-urban")
        a = case["nodes"]["302372908"]
        b = case["nodes"]["302372907"]
        with patch(
            "workspace_service.shortest_route",
            return_value={"metres": None, "path": []},
        ):
            result = self.workspace.resolve_custom(case, {
                "origin": a, "destination": b,
            })
        self.assertEqual(result["status"], "no_baseline_route")


class PlaceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = hamar_workspace.WorkspaceServer(0, opener=FakeOpener())
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, path):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.server_address[1]}{path}"
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def test_search_http_contract(self):
        status, body = self.call("/api/places?q=Storhamarsenteret")
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertTrue(result["matches"])
        self.assertEqual(self.call("/api/places/nope?q=x")[0], 404)
        self.assertEqual(self.call("/api/places?q=")[0], 400)
        self.assertEqual(self.call("/api/places?q=" + "x" * 81)[0], 400)


class SavedJourneyClientTests(unittest.TestCase):
    def test_client_uses_local_storage_and_reuses_custom_engine(self):
        script = (ROOT / "workspace" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "workspace" / "index.html").read_text(encoding="utf-8")
        self.assertIn("localStorage.setItem", script)
        self.assertIn("localStorage.getItem", script)
        self.assertIn("/api/places?q=", script)
        self.assertIn("resolveCustom()", script)
        restore = script[script.index("async function restoreSavedJourney"):
                         script.index("function deleteSavedJourney")]
        self.assertIn("await assess()", restore)
        self.assertNotIn("Select Assess projects", restore)
        self.assertIn("data-delete-saved", script)
        self.assertIn("invalid and was not loaded", script)
        self.assertRegex(script, r"(?m)^function endpointLabel\(")
        self.assertIn('id="place-from"', html)
        self.assertIn('id="place-to"', html)
        self.assertIn("Walking scope:", script)
        self.assertNotIn("new WebSocket", script)
        self.assertNotIn("geocode", script.lower())


if __name__ == "__main__":
    unittest.main()
