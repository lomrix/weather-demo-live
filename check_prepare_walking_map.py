"""Synthetic, offline checks for walking-map preparation."""

import hashlib
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from harness.prepare_walking_map import prepare


class Response:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.data


class PreparationTests(unittest.TestCase):
    def test_tiles_merge_sanitize_and_record_exact_bounds(self):
        urls = []

        def opener(request, timeout):
            urls.append(request.full_url)
            west, south, east, north = parse_qs(urlparse(request.full_url).query)["bbox"][0].split(",")
            return Response(f'''<osm version="0.6"><bounds minlat="{south}" minlon="{west}"
                maxlat="{north}" maxlon="{east}"/>
                <node id="1" lat="1" lon="2" user="private"/>
                <node id="2" lat="1" lon="2.1" uid="1"/>
                <way id="3"><nd ref="1"/><nd ref="2"/>
                <tag k="highway" v="footway"/><tag k="phone" v="private"/></way></osm>'''.encode())

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "map.osm"
            entry = prepare((2, 1, 2.2, 1.1), 2, 1, output, opener)
            raw = output.read_bytes()
            root = ET.fromstring(raw)
            self.assertEqual(len(urls), 2)
            self.assertEqual((len(root.findall("node")), len(root.findall("way"))), (2, 1))
            self.assertNotIn(b"private", raw)
            self.assertEqual(entry["sanitized_fixture_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(entry["bounds"], {"minlat": 1, "minlon": 2, "maxlat": 1.1, "maxlon": 2.2})
            self.assertEqual(len(entry["source_tiles"]), 2)

    def test_bad_bounds_and_response_fail_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "map.osm"
            with self.assertRaises(ValueError):
                prepare((2, 1, 2, 1.1), 1, 1, output)
            with self.assertRaises(ValueError):
                prepare((0, 0, 1, 1), 1, 1, output)
            with self.assertRaises(ValueError):
                prepare((2, 1, 2.1, 1.1), 1, 1, output,
                        lambda request, timeout: Response(b"<osm/>"))
            missing_node_tile = (
                b'<osm><bounds minlon="2" minlat="1" maxlon="2.1" maxlat="1.1"/>'
                b'<way id="1"><nd ref="99"/><tag k="highway" v="footway"/></way></osm>'
            )
            with self.assertRaisesRegex(ValueError, "missing nodes"):
                prepare((2, 1, 2.1, 1.1), 1, 1, output,
                        lambda request, timeout: Response(missing_node_tile))
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
