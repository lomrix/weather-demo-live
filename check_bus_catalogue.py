"""Offline bus inventory boundary, source-integrity and geometry checks."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from harness.import_hamar_bus import in_boundary, discover, data_response, decode_geometry
from harness.bus_catalogue import load, query

ROOT=Path(__file__).resolve().parent

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.geometry={'type':'Polygon','coordinates':[[[0,0],[10,0],[10,10],[0,10],[0,0]],[[4,4],[6,4],[6,6],[4,6],[4,4]]]}
        self.boundary={'kommunenummer':'3403','omrade':self.geometry}
        self.bus={'id':'TEST:Line:1','publicCode':'T1','name':'Synthetic test bus','transportMode':'bus'}

    def test_polygon_holes_and_outside_are_excluded(self):
        self.assertTrue(in_boundary(2,2,self.geometry))
        self.assertFalse(in_boundary(5,5,self.geometry))
        self.assertFalse(in_boundary(11,5,self.geometry))

    def test_multipolygon_preserves_separate_islands(self):
        geometry={'type':'MultiPolygon','coordinates':[self.geometry['coordinates'],[[[20,20],[21,20],[21,21],[20,21],[20,20]]]]}
        self.assertTrue(in_boundary(20.5,20.5,geometry))
        self.assertFalse(in_boundary(15,15,geometry))

    def test_discovery_uses_quay_coordinates_and_bus_mode(self):
        quay=lambda identifier,lat,lon,lines:{'id':identifier,'name':identifier,'latitude':lat,'longitude':lon,'lines':lines}
        response={'stopPlacesByBbox':[{'id':'STOP:1','name':'Synthetic','latitude':99,'longitude':99,'quays':[
            quay('Q1',2,2,[self.bus]),quay('Q2',11,2,[{**self.bus,'id':'TEST:Line:2'}]),
            quay('Q3',3,3,[{**self.bus,'transportMode':'rail','id':'TEST:Line:3'}]),
            quay('Q4',5,5,[{**self.bus,'id':'TEST:Line:4'}])]}]}
        lines,quays=discover(self.boundary,response)
        self.assertEqual(set(lines),{'TEST:Line:1'})
        self.assertEqual(set(quays),{'Q1'})

    def test_empty_results_do_not_claim_complete_inventory(self):
        with self.assertRaisesRegex(ValueError,'No Hamar'):discover(self.boundary,{'stopPlacesByBbox':[]})

    def test_partial_graphql_response_is_rejected(self):
        with self.assertRaises(ValueError):data_response(b'{"data":{"lines":[]},"errors":[{"message":"partial"}]}')

    def test_encoded_geometry_coordinate_order(self):
        self.assertEqual(decode_geometry('_p~iF~ps|U_ulLnnqC_mqNvxq`@'),[[-120.2,38.5],[-120.95,40.7],[-126.453,43.252]])

    def test_truncated_and_invalid_geometry_rejected(self):
        for encoded in ('_', '\u0000'):
            with self.subTest(encoded=encoded),self.assertRaises(ValueError):decode_geometry(encoded)

class SavedCatalogueTests(unittest.TestCase):
    def test_saved_inventory_has_additional_real_services(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('Offline catalogue must not fetch')):
            result=query(ROOT)
        codes={line['code'] for line in result['lines']}
        self.assertTrue({'B21','B22','B23','B24','B25','B26','B27'}<=codes)
        self.assertEqual(result['line_count'],len(result['lines']))
        self.assertEqual(result['scope']['municipality_code'],'3403')
        self.assertFalse(result['scope']['external_completeness_verified'])

    def test_full_stop_order_geometry_and_date_identity(self):
        catalogue=query(ROOT)
        line=next(line for line in catalogue['lines'] if line['code']=='B22')
        detail=query(ROOT,line['id']);self.assertTrue(detail['patterns'])
        result=query(ROOT,line['id'],detail['patterns'][0]['id'])
        pattern=result['pattern']
        self.assertEqual(pattern['stops'][0]['name'],detail['patterns'][0]['first_stop'])
        self.assertEqual(pattern['stops'][-1]['name'],detail['patterns'][0]['last_stop'])
        self.assertEqual(pattern['scheduled_journey_count'],len(pattern['scheduled_journey_ids']))
        self.assertEqual(result['service_date'],'2026-11-19')
        self.assertTrue(any(stop['in_hamar'] for stop in pattern['stops']))
        self.assertGreater(len(pattern['geometry']),1)
        self.assertTrue(all(-180<=p[0]<=180 and -90<=p[1]<=90 for p in pattern['geometry']))

    def test_unknown_line_and_variant_are_rejected(self):
        with self.assertRaises(LookupError):query(ROOT,'../../anything')
        with self.assertRaises(LookupError):query(ROOT,query(ROOT)['lines'][0]['id'],'missing-pattern')

    def test_source_tampering_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination=Path(temporary)/'fixtures'/'transit'/'hamar'
            shutil.copytree(ROOT/'fixtures'/'transit'/'hamar',destination)
            with (destination/'discovery.json').open('ab') as changed:changed.write(b' ')
            with self.assertRaisesRegex(ValueError,'checksum'):load(temporary)

if __name__=='__main__':unittest.main()
