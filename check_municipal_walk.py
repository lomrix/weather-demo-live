"""Offline municipal network, access policy and normal-journey regressions."""
import hashlib
import json
import unittest
import tempfile
from harness.prepare_municipal_walk import prepare, project
from pathlib import Path

from harness.municipal_walk import allowed, blocked_node, streets
from harness.workspace_service import Workspace
from harness.scenario_compare import shortest_route

ROOT=Path(__file__).resolve().parent


class MunicipalWalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace=Workspace()
        cls.case=cls.workspace.get_case('hamar-municipality')

    def test_source_integrity_and_reproducible_street_index(self):
        source=ROOT/'fixtures/maps/hamar-municipality.json'
        data=json.loads(source.read_text(encoding='utf-8'))
        index_path=ROOT/'fixtures/maps/hamar-municipality-streets.json'
        index=json.loads(index_path.read_text(encoding='utf-8'))
        self.assertEqual(index['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(index['streets'],streets(data))
        self.assertEqual(hashlib.sha256(index_path.read_bytes()).hexdigest(),self.case['manifest']['street_index_sha256'])
        self.assertEqual(data['area']['ref'],'3403')
        self.assertEqual(len([e for e in data['elements'] if e['type']=='way']),8415)
        self.assertTrue(any(s['name']=='Seminargata' for s in index['streets']))

    def test_allowlist_excludes_personal_and_contact_fields(self):
        data=json.loads((ROOT/'fixtures/maps/hamar-municipality.json').read_text(encoding='utf-8'))
        permitted={'highway','foot','access','motorroad','name','barrier','sidewalk','surface','incline','foot:conditional','access:conditional','oneway:foot'}
        for element in data['elements']:
            self.assertTrue(set(element)<= {'type','id','lat','lon','nodes','tags'})
            self.assertTrue(set(element['tags'])<=permitted)

    def test_residential_roads_and_restricted_roads(self):
        self.assertTrue(allowed({'highway':'residential'}))
        self.assertTrue(allowed({'highway':'service','access':'private','foot':'yes'}))
        for tags in ({'highway':'motorway'},{'highway':'primary','motorroad':'yes'},
                     {'highway':'path','foot':'no'},{'highway':'service','access':'private'},
                     {'highway':'path','foot':'destination'},{'highway':'residential','foot:conditional':'no @ (Mo-Fr)'},
                     {'highway':'construction'},{'highway':'primary','foot':'use_sidepath'}):
            self.assertFalse(allowed(tags),tags)
        self.assertTrue(blocked_node({'barrier':'wall'}))
        self.assertTrue(blocked_node({'barrier':'gate','access':'private'}))
        self.assertFalse(blocked_node({'barrier':'gate','access':'private','foot':'yes'}))

    def test_explicit_oneway_foot_is_respected(self):
        network=[{'id':'one','from':'a','to':'b','metres':10,'modes':['walking'],'walking_oneway':True}]
        self.assertEqual(shortest_route(network,'a','b')['metres'],10)
        self.assertIsNone(shortest_route(network,'b','a')['metres'])
        network[0]['walking_oneway']=False
        self.assertEqual(shortest_route(network,'b','a')['metres'],10)

    def test_graph_links_are_complete_and_long_edges_are_subdivided(self):
        self.assertGreater(self.case['coverage']['maxlat'],60.9)
        self.assertGreater(self.case['coverage']['maxlon'],11.2)
        self.assertGreater(len(self.case['links']),70000)
        self.assertEqual(self.case['sections'],[])
        self.assertTrue(all(link['from'] in self.case['nodes'] and link['to'] in self.case['nodes'] for link in self.case['links'].values()))
        self.assertLessEqual(max(link['metres'] for link in self.case['links'].values()),51)
        self.assertGreater(self.case['statistics']['components'],1)

    def test_rural_route_outside_old_extract_and_zero_closure_assessment(self):
        request={'case_id':'hamar-municipality','assessment_date':'2026-11-24','projects':[],
                 'custom_journey':{'origin':{'lat':60.794983916826205,'lon':11.072413135617717},
                                   'destination':{'lat':60.88916901465523,'lon':11.197857392305103}}}
        resolved=self.workspace.resolve_journey({k:request[k] for k in ('case_id','custom_journey')})
        self.assertEqual(resolved['status'],'ready')
        self.assertGreater(resolved['baseline_metres'],10000)
        old=self.workspace.resolve_journey({**{k:request[k] for k in ('case_id','custom_journey')},'case_id':'hamar-urban'})
        self.assertEqual(old['status'],'outside_coverage')
        result=self.workspace.assess(request)
        self.assertFalse(result['hypothetical'])
        self.assertEqual(result['active_projects'],[])
        self.assertEqual(result['closed_link_ids'],[])
        self.assertEqual(result['custom_journey']['row']['baseline_metres'],resolved['baseline_metres'])
        self.assertEqual(result['custom_journey']['row']['metres'],resolved['baseline_metres'])

    def test_real_source_disconnection_is_not_bridged(self):
        # Synthetic graph: geometric overlap is not permission to invent a crossing.
        network=[{'id':'ab','from':'a','to':'b','metres':10,'modes':['walking']},
                 {'id':'cd','from':'c','to':'d','metres':10,'modes':['walking']}]
        self.assertIsNone(shortest_route(network,'a','d')['metres'])

    def test_payload_contains_municipal_boundary_and_keeps_legacy_cases(self):
        payload=self.workspace.case_payload('hamar-municipality')
        self.assertTrue(payload['municipal'])
        self.assertEqual(payload['boundary']['type'],'MultiPolygon')
        self.assertEqual(payload['candidates'],[])
        self.assertEqual(payload['sections'],[])
        self.assertEqual(self.workspace.get_case('koigen-demo')['journeys'][0]['baseline_metres'],323)
        self.assertIn('hamar-urban',self.workspace.cases)


class MunicipalCaptureTests(unittest.TestCase):
    def test_saved_replay_is_byte_identical_and_does_not_request_network(self):
        def no_network(*args, **kwargs):
            raise AssertionError("Offline replay must not make a request")
        source=ROOT/'fixtures/maps/hamar-municipality.json'
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'replay'
            summary=prepare(output,source=source,opener=no_network)
            self.assertFalse(summary['live_request'])
            self.assertTrue((output/'hamar-municipality-streets.json').read_bytes().endswith(b'\r\n'))
            self.assertEqual((output/'hamar-municipality.json').read_bytes(),source.read_bytes())
            self.assertEqual((output/'hamar-municipality-streets.json').read_bytes(),(ROOT/'fixtures/maps/hamar-municipality-streets.json').read_bytes())
            with self.assertRaisesRegex(ValueError,'already exists'):
                prepare(output,source=source,opener=no_network)

    def test_live_projection_removes_contributors_and_unneeded_tags(self):
        data={'elements':[{'type':'area','id':1,'tags':{'ref':'3403','name':'Hamar'}},
                          {'type':'node','id':2,'lat':60.8,'lon':11.1,'user':'synthetic-contributor','tags':{'phone':'synthetic-contact'}},
                          {'type':'node','id':3,'lat':60.801,'lon':11.1},
                          {'type':'way','id':4,'nodes':[2,3],'tags':{'highway':'residential','name':'Synthetic street','contact:email':'synthetic-contact'}}]}
        saved=project(json.dumps(data).encode())
        self.assertFalse(any('user' in item for item in saved['elements']))
        self.assertNotIn('synthetic-contact',json.dumps(saved))
        self.assertEqual(saved['area']['ref'],'3403')
        data['elements'][0]['tags']['ref']='0301'
        with self.assertRaisesRegex(ValueError,'Hamar'):
            project(json.dumps(data).encode())


if __name__=='__main__':unittest.main()
