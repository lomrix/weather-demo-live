"""Offline regression evidence for route snapping and local-model stop conditions."""
import copy
import io
import json
import unittest
from unittest.mock import patch
from urllib.request import Request

from harness.model_budget import LocalModelRun, BudgetStop, ENDPOINT, PROMPT_BYTES
from harness.municipal_snap import resolve, network_for
from harness.scenario_compare import shortest_route
from harness.workspace_service import Workspace
from check_notice_evidence import koigen_reply


def synthetic_case(oneway=False):
    edge={'id':'edge','from':'a','to':'b','metres':100,'modes':['walking'],
          'source':'https://www.openstreetmap.org/way/1','walking_oneway':oneway}
    return {'nodes':{'a':[60,11],'b':[60+100/111320,11]},'links':{'edge':edge},
            'scenario':{'network':[edge]},'coverage':{'minlat':59,'maxlat':61,'minlon':10,'maxlon':12}}


def point(metres,east=0):return [60+metres/111320,11+east/(111320*0.5)]
def route(case,a,b):return resolve(case,{'origin':a,'destination':b},shortest_route,lambda *_:[])


class SegmentSnapTests(unittest.TestCase):
    def test_two_nearby_points_on_same_edge_remain_distinct(self):
        result=route(synthetic_case(),point(20,5),point(40,5))
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['baseline_metres'],20)
        self.assertNotEqual(result['origin']['node_id'],result['destination']['node_id'])
        self.assertAlmostEqual(result['origin']['snap_metres'],5,places=1)

    def test_directed_walking_edge_does_not_gain_a_reverse_connection(self):
        self.assertEqual(route(synthetic_case(True),point(20),point(80))['baseline_metres'],60)
        self.assertEqual(route(synthetic_case(True),point(80),point(20))['status'],'no_baseline_route')

    def test_no_join_is_invented_between_close_parallel_roads(self):
        case=synthetic_case();case['nodes'].update({'c':point(0,10),'d':point(100,10)})
        edge={'id':'other','from':'c','to':'d','metres':100,'modes':['walking'],'source':'https://www.openstreetmap.org/way/2'}
        case['links']['other']=edge;case['scenario']['network'].append(edge)
        self.assertEqual(route(case,point(20),point(80,10))['status'],'no_baseline_route')

    def test_overlay_preserves_base_graph_and_integer_segment_length(self):
        case=synthetic_case();before=copy.deepcopy(case)
        result=route(case,point(20),point(80))
        self.assertEqual(case,before)
        self.assertEqual(sum(e['metres'] for e in network_for(case,result['routing_overlay'])),100)
        self.assertEqual(result['status'],'ready')

    def test_identical_projected_connections_and_off_network_points(self):
        self.assertEqual(route(synthetic_case(),point(20),point(20))['status'],'same_place')
        self.assertEqual(route(synthetic_case(),point(20),point(80,100))['status'],'outside_coverage')


class BudgetTests(unittest.TestCase):
    def setUp(self):self.calls=[]
    def open(self,request,timeout):
        self.calls.append(json.loads(request.data))
        return io.BytesIO(json.dumps({'response':'{}','prompt_eval_count':100,'eval_count':20}).encode())
    def request(self,**changes):
        data={'model':'qwen2.5:3b','prompt':'A synthetic prompt','options':{'num_predict':700}}
        data.update(changes)
        return Request(ENDPOINT,data=json.dumps(data).encode(),method='POST')

    def test_limits_are_sent_and_second_request_cannot_start(self):
        run=LocalModelRun(self.open)
        with run.open(self.request(),10) as response:response.read(16385)
        self.assertEqual(self.calls[0]['options']['num_ctx'],4096)
        self.assertEqual(self.calls[0]['options']['num_predict'],700)
        with self.assertRaisesRegex(BudgetStop,'exhausted'):run.open(self.request(),10)
        self.assertEqual(len(self.calls),1)

    def test_remote_endpoint_and_oversized_prompt_are_rejected_before_transport(self):
        bad=Request('https://unapproved.invalid/generate',data=b'{}',method='POST')
        for request in (bad,self.request(prompt='x'*(PROMPT_BYTES+1))):
            with self.assertRaises(BudgetStop):LocalModelRun(self.open).open(request,10)
        self.assertFalse(self.calls)

    def test_unlimited_or_over_budget_generation_is_rejected(self):
        for value in (-1,701,True):
            with self.assertRaises(BudgetStop):LocalModelRun(self.open).open(self.request(options={'num_predict':value}),10)
        self.assertFalse(self.calls)

    def test_reported_token_overrun_discards_the_response(self):
        def bad(request,timeout):return io.BytesIO(json.dumps({'response':'{}','eval_count':701}).encode())
        run=LocalModelRun(bad)
        with self.assertRaisesRegex(BudgetStop,'reported token'):
            with run.open(self.request(),10) as response:response.read(16385)
        with self.assertRaisesRegex(BudgetStop,'exhausted'):run.open(self.request(),10)


class ApplicationStopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls=[]
        def opener(request,timeout):
            cls.calls.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'response':json.dumps(koigen_reply()),'prompt_eval_count':300,'eval_count':150}).encode())
        cls.workspace=Workspace(opener=opener)

    def test_pause_blocks_new_ai_requests_but_manual_walking_works(self):
        workspace=self.workspace;self.calls.clear()
        workspace.ai_control({'enabled':False})
        try:
            with self.assertRaisesRegex(ValueError,'paused'):
                workspace.draft_koigen_notice({'notice_id':'hamar-koigen-footpath'})
            self.assertFalse(self.calls)
            result=workspace.assess({'case_id':'hamar-municipality','assessment_date':'2026-11-25','projects':[],
                                    'custom_journey':{'origin':{'lat':60.794983916826205,'lon':11.072413135617717},
                                                      'destination':{'lat':60.79512048519726,'lon':11.072293321609518}}})
            self.assertGreater(result['custom_journey']['row']['metres'],0)
            self.assertFalse(self.calls)
        finally:workspace.ai_control({'enabled':True})
        result=workspace.draft_koigen_notice({'notice_id':'hamar-koigen-footpath'})
        self.assertEqual(result['state'],'success')
        self.assertEqual(len(self.calls),1)

    def test_default_model_transport_refuses_redirects(self):
        import urllib.request
        from harness.model_budget import NoRedirect
        previous=self.workspace.opener
        self.workspace.opener=urllib.request.urlopen
        try:
            with patch('urllib.request.build_opener') as builder:
                self.workspace._model_open(Request(ENDPOINT,data=b'{}'),10)
                self.assertIsInstance(builder.call_args.args[0],NoRedirect)
        finally:self.workspace.opener=previous

    def test_hypothetical_closure_accepts_projected_route_sections(self):
        w=self.workspace
        custom={'origin':{'lat':60.794983916826205,'lon':11.072413135617717},'destination':{'lat':60.79512048519726,'lon':11.072293321609518}}
        resolved=w.resolve_journey({'case_id':'hamar-municipality','custom_journey':custom})
        section=resolved['sections'][0]['id']
        result=w.assess({'case_id':'hamar-municipality','custom_journey':custom,'assessment_date':'2026-11-25',
                         'projects':[{'name':'Synthetic short-route closure','start_date':'2026-11-25','end_date':'2026-11-25','sections':[section],'hypothetical':True}]})
        self.assertTrue(result['active_projects'])
        self.assertIn(result['custom_journey']['row']['status'],('unreachable','longer'))


if __name__=='__main__':unittest.main()
