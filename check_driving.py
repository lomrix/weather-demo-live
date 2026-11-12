"""Synthetic checks of OSM car access, direction and dated road closures."""

import tempfile
import unittest
from pathlib import Path

from harness.import_driving_osm import import_roads
from harness.project_scenario import assess_projects
from harness.sanitize_driving_fixture import sanitize
from harness.scenario_compare import shortest_route


OSM = b"""<osm version="0.6"><bounds minlat="60" minlon="11" maxlat="61" maxlon="12"/>
<node id="1" lat="60" lon="11" user="private"/>
<node id="2" lat="60" lon="11.001"/>
<node id="3" lat="60" lon="11.002"/>
<node id="4" lat="60.001" lon="11.001"/>
<node id="5" lat="60" lon="11.003"/>
<node id="6" lat="60" lon="11.004"><tag k="barrier" v="bollard"/></node>
<node id="7" lat="60.002" lon="11.001"/>
<node id="8" lat="60.002" lon="11.002"/>
<way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/><tag k="oneway" v="yes"/></way>
<way id="11"><nd ref="2"/><nd ref="3"/><tag k="highway" v="residential"/><tag k="motorcar" v="no"/></way>
<way id="12"><nd ref="2"/><nd ref="4"/><nd ref="3"/><tag k="highway" v="residential"/></way>
<way id="13"><nd ref="3"/><nd ref="5"/><tag k="highway" v="residential"/><tag k="junction" v="roundabout"/></way>
<way id="14"><nd ref="5"/><nd ref="6"/><tag k="highway" v="service"/></way>
<way id="15"><nd ref="1"/><nd ref="3"/><tag k="highway" v="residential"/><tag k="access:conditional" v="no @ (Mo-Fr)"/></way>
<way id="16"><nd ref="1"/><nd ref="4"/><tag k="highway" v="residential"/><tag k="oneway" v="-1"/></way>
<way id="17"><nd ref="7"/><nd ref="8"/><tag k="highway" v="residential"/><tag k="access" v="no"/><tag k="motorcar" v="yes"/><tag k="oneway" v="yes"/><tag k="oneway:motorcar" v="no"/></way>
</osm>"""


class DrivingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        source = Path(self.tmp.name) / "source.osm"
        fixture = Path(self.tmp.name) / "roads.osm"
        source.write_bytes(OSM)
        sanitize(source, fixture)
        self.assertNotIn(b'user="private"', fixture.read_bytes())
        self.graph = import_roads(fixture)["network"]

    def route(self, start, end, closed=None):
        return shortest_route(self.graph, start, end, closed, mode="vehicle")

    def test_one_way_and_roundabout_are_directional(self):
        self.assertEqual(self.route("1", "2")["path"], ("1", "2"))
        self.assertEqual(self.route("2", "1")["path"], ("2", "4", "1"))
        self.assertEqual(self.route("3", "5")["path"], ("3", "5"))
        self.assertIsNone(self.route("5", "3")["metres"])
        self.assertEqual(self.route("4", "1")["path"], ("4", "1"))
        self.assertEqual(self.route("1", "4")["path"], ("1", "2", "4"))
        self.assertEqual(self.route("7", "8")["path"], ("7", "8"))
        self.assertEqual(self.route("8", "7")["path"], ("8", "7"))

    def test_car_restriction_conditional_and_barrier_excluded(self):
        ids = {link["id"] for link in self.graph}
        self.assertNotIn("osm-road-11-segment-1", ids)
        self.assertNotIn("osm-road-15-segment-1", ids)
        self.assertNotIn("osm-road-14-segment-1", ids)
        self.assertEqual(self.route("1", "3")["path"], ("1", "2", "4", "3"))

    def test_dated_road_closure_changes_route_and_cannot_be_crossed(self):
        scenario = {
            "routing_mode": "vehicle", "network": self.graph,
            "journeys": [{"id": "trip", "origin": "1", "destination": "3"}],
            "projects": [{"id": "p", "label": "Hypothetical", "hypothetical": True,
                          "start_date": "2026-05-01", "end_date": "2026-05-01",
                          "restrictions": [{"type": "restrict_links", "mode": "vehicle",
                                            "link_ids": ["osm-road-12-segment-1"]}]}],
        }
        active = assess_projects(scenario, "2026-05-01")["comparison"]["alternatives"][0]["journeys"][0]
        inactive = assess_projects(scenario, "2026-05-02")["comparison"]["alternatives"][0]["journeys"][0]
        self.assertEqual(active["baseline"]["path"], ("1", "2", "4", "3"))
        self.assertEqual(active["status"], "unreachable")
        self.assertEqual(inactive["route"]["path"], inactive["baseline"]["path"])


if __name__ == "__main__":
    unittest.main()
