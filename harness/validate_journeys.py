"""Repeatable offline validation of frozen source-backed municipal journeys.

Separates contract checks, path integrity, independent distance checking and
timing. These are software/graph tests, not human validation of real-world access.
"""
import argparse
import hashlib
import heapq
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .workspace_service import Workspace

ROOT=Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_distance(network, origin, destination):
    """Independent distance-only Dijkstra; does not call the production router."""
    graph={}
    for edge in network:
        graph.setdefault(edge['from'],[]).append((edge['to'],edge['metres']))
        if not edge.get('walking_oneway',False):
            graph.setdefault(edge['to'],[]).append((edge['from'],edge['metres']))
    distance={origin:0};queue=[(0,origin)]
    while queue:
        value,node=heapq.heappop(queue)
        if value!=distance[node]:continue
        if node==destination:return value
        for other,weight in graph.get(node,[]):
            candidate=value+weight
            if candidate<distance.get(other,float('inf')):
                distance[other]=candidate;heapq.heappush(queue,(candidate,other))
    return None


def check_path(network,result):
    weights={}
    for edge in network:
        directions=[(edge['from'],edge['to'])]
        if not edge.get('walking_oneway',False):directions.append((edge['to'],edge['from']))
        for pair in directions:weights[pair]=min(weights.get(pair,float('inf')),edge['metres'])
    path=result['baseline_path']
    if not path or path[0]!=result['origin']['node_id'] or path[-1]!=result['destination']['node_id']:
        return False
    pairs=list(zip(path,path[1:]))
    return all(pair in weights for pair in pairs) and sum(weights[pair] for pair in pairs)==result['baseline_metres']


def evaluate(cases_path,root=ROOT,legacy_node_snap=False):
    root=Path(root);spec=json.loads(Path(cases_path).read_text(encoding='utf-8'))
    if digest(root/'fixtures/maps/hamar-municipality.json')!=spec['source_sha256']:
        raise ValueError('Frozen route source checksum mismatch')
    workspace=Workspace(root);case=workspace.get_case('hamar-municipality');rows=[]
    if legacy_node_snap:workspace.resolve_custom=workspace._resolve_custom_nodes
    for item in spec['cases']:
        request={'case_id':'hamar-municipality','custom_journey':{
            side:dict(zip(('lat','lon'),item[label]['coordinates']))
            for side,label in (('origin','origin'),('destination','destination'))}}
        started=perf_counter()
        try:
            result=workspace.resolve_journey(request)
        except ValueError as error:
            result={'status':'rejected','message':str(error)}
        elapsed=perf_counter()-started
        status=result['status'];path_ok=optimal=None
        if status=='ready':
            overlay=result.get('routing_overlay',{})
            removed=set(overlay.get('removed_link_ids',[]))
            network=[link for link in case['scenario']['network'] if link['id'] not in removed]+overlay.get('links',[])
            path_ok=check_path(network,result)
            optimal=independent_distance(network,result['origin']['node_id'],result['destination']['node_id'])==result['baseline_metres']
        rows.append({'id':item['id'],'kind':item['kind'],'expected_status':item['expected_status'],
                     'actual_status':status,'passed':status==item['expected_status'] and path_ok is not False and optimal is not False,
                     'network_metres':result.get('baseline_metres'),'path_valid':path_ok,'independent_distance_match':optimal,
                     'elapsed_seconds':round(elapsed,4),
                     'origin_snap_metres':result.get('origin',{}).get('snap_metres'),
                     'destination_snap_metres':result.get('destination',{}).get('snap_metres'),
                     'message':result.get('message')})
    passed=sum(row['passed'] for row in rows)
    return {'id':spec['id'],'checked_at':datetime.now(timezone.utc).isoformat(),
            'algorithm':'legacy-nearest-node' if legacy_node_snap else 'municipal-edge-snap-v1',
            'cases_sha256':digest(cases_path),'source_sha256':spec['source_sha256'],
            'code_sha256':{str(path):digest(root/path) for path in (
                Path('harness/workspace_service.py'),Path('harness/scenario_compare.py'),Path('harness/municipal_walk.py'),Path('harness/municipal_snap.py'),Path('harness/validate_journeys.py'))},
            'summary':{'passed':passed,'total':len(rows),'ready_routes':sum(row['actual_status']=='ready' for row in rows),
                       'median_seconds':round(statistics.median(row['elapsed_seconds'] for row in rows),4),
                       'maximum_seconds':max(row['elapsed_seconds'] for row in rows)},
            'reference_scope':spec['reference_scope'],'results':rows}


def save_report(report,output):
    output=Path(output)
    if output.exists():raise ValueError('Choose a new evaluation directory; previous runs are preserved')
    output.mkdir(parents=True)
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Frozen municipal journey validation','',f"Passed: {report['summary']['passed']}/{report['summary']['total']}.",
           '',report['reference_scope'],'',
           '| Case | Expected | Actual | Network m | Path / optimality | Seconds |',
           '| --- | --- | --- | ---: | --- | ---: |']
    for row in report['results']:
        lines.append(f"| {row['id']} | {row['expected_status']} | {row['actual_status']} | {row['network_metres']} | {row['path_valid']} / {row['independent_distance_match']} | {row['elapsed_seconds']} |")
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,default=ROOT/'fixtures/evaluation/municipal-journeys.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--legacy-node-snap',action='store_true',help='Reproduce the previous snapping behavior for the failure comparison')
    args=parser.parse_args()
    if args.output.exists():parser.error('Output directory already exists')
    report=evaluate(args.cases,legacy_node_snap=args.legacy_node_snap);save_report(report,args.output)
    print(json.dumps(report['summary']))
    raise SystemExit(0 if report['summary']['passed']==report['summary']['total'] else 1)


if __name__=='__main__':main()
