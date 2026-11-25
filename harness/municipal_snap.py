"""Request-local endpoint projection onto municipal walking edges.

Splits only existing links. No straight-line address connector is added to the
walking graph, and different roads are never joined by proximity.
"""
import math

VERSION='municipal-edge-snap-v1'


def locate(case,point,label,limit=75):
    lat,lon=point;coverage=case['coverage'];base={'requested':list(point)}
    if not (coverage['minlat']<=lat<=coverage['maxlat'] and coverage['minlon']<=lon<=coverage['maxlon']):
        return {**base,'status':'outside_coverage','reason':'outside_extract','message':f'{label} is outside the municipal walking map.'}
    scale=111320*math.cos(math.radians(lat));dy=limit/111320;dx=limit/scale
    best=None
    for link in case['scenario']['network']:
        a,b=case['nodes'][link['from']],case['nodes'][link['to']]
        if max(a[0],b[0])<lat-dy or min(a[0],b[0])>lat+dy or max(a[1],b[1])<lon-dx or min(a[1],b[1])>lon+dx:
            continue
        ax,ay=(a[1]-lon)*scale,(a[0]-lat)*111320
        vx,vy=(b[1]-a[1])*scale,(b[0]-a[0])*111320
        denominator=vx*vx+vy*vy
        fraction=max(0,min(1,-(ax*vx+ay*vy)/denominator)) if denominator else 0
        distance=math.hypot(ax+fraction*vx,ay+fraction*vy)
        candidate=(distance,link['id'],fraction)
        if best is None or candidate<best:best=candidate
    if best is None or best[0]>limit:
        return {**base,'status':'outside_coverage','reason':'no_walking_network_nearby',
                'message':f'{label} has no mapped pedestrian connection within {limit} m.'}
    distance,link_id,fraction=best;link=case['links'][link_id]
    a,b=case['nodes'][link['from']],case['nodes'][link['to']]
    node=link['from'] if fraction<=1e-8 else link['to'] if fraction>=1-1e-8 else None
    return {**base,'status':'snapped','node_id':node,'edge_id':link_id,'edge_fraction':fraction,
            'snapped':[a[i]+fraction*(b[i]-a[i]) for i in (0,1)],'snap_metres':round(distance,1),
            'message':f'{label} is {distance:.1f} m from its mapped walking connection; this access offset is not part of the route distance.'}


def overlay_for(case,origin,destination):
    overlay={'nodes':{},'links':[],'removed_link_ids':[],'version':VERSION}
    groups={}
    for side,snap in (('origin',origin),('destination',destination)):
        if snap['status']=='snapped' and snap['node_id'] is None:
            groups.setdefault(snap['edge_id'],[]).append((snap['edge_fraction'],side,snap))
    for link_id,items in groups.items():
        link=case['links'][link_id];overlay['removed_link_ids'].append(link_id)
        cuts=[(0,link['from'])]
        for fraction,side,snap in sorted(items,key=lambda item:(item[0],item[1])):
            # Equal projected positions share a connection; distinct positions
            # remain distinct even when the original OSM vertices are distant.
            if fraction-cuts[-1][0]<1e-8:
                snap['node_id']=cuts[-1][1]
                continue
            node='journey-snap-'+side;snap['node_id']=node
            overlay['nodes'][node]=snap['snapped'];cuts.append((fraction,node))
        cuts.append((1,link['to']))
        for index,((start,a),(end,b)) in enumerate(zip(cuts,cuts[1:]),1):
            length=max(1,round(link['metres']*end)-round(link['metres']*start))
            overlay['links'].append({**link,'id':link_id+'-snap-'+str(index),'from':a,'to':b,'metres':length})
    return overlay


def network_for(case,overlay):
    removed=set(overlay.get('removed_link_ids',[]))
    return [link for link in case['scenario']['network'] if link['id'] not in removed]+overlay.get('links',[])


def resolve(case,custom,shortest,sections,limit=75):
    origin=locate(case,custom['origin'],'Start',limit)
    destination=locate(case,custom['destination'],'Destination',limit)
    overlay=overlay_for(case,origin,destination)
    result={'id':'custom','origin':origin,'destination':destination,'sections':[],
            'baseline_metres':None,'baseline_path':[],'routing_overlay':overlay,
            'distance_scope':'Mapped walking network only; address access offsets excluded.'}
    if origin['status']!='snapped' or destination['status']!='snapped':
        result.update(status='outside_coverage',message='An endpoint has no mapped connection within the supported distance. No connection has been invented.')
    elif origin['node_id']==destination['node_id']:
        result.update(status='same_place',message='Both endpoints project to the same walking connection. Address access offsets are not a mapped walking route.')
    else:
        network=network_for(case,overlay)
        route=shortest(network,origin['node_id'],destination['node_id'])
        if route['metres'] is None:
            result.update(status='no_baseline_route',message='The mapped connections are disconnected or direction-restricted. No crossing or bridge has been invented.')
        else:
            result.update(status='ready',message='Endpoints connect through the mapped walking network.',baseline_metres=route['metres'],baseline_path=list(route['path']))
            links={link['id']:link for link in network}
            result['sections']=sections({'links':links},route['path'])
    return result
