"""Bounded Entur bus discovery against Kartverket's Hamar municipal polygon.

Live acquisition is explicit. Replay uses the exact saved responses and query.
No credentials, live delays or pedestrian routing are involved.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ENDPOINT = 'https://api.entur.io/journey-planner/v3/graphql'
BOUNDARY = 'https://api.kartverket.no/kommuneinfo/v1/kommuner/3403/omrade'
CLIENT = 'lomrix-hamar-access-lab'
MAX_BYTES = 16 * 1024 * 1024
TIMEOUT = 30
ROOT = Path(__file__).resolve().parents[1]
DISCOVER = '''query HamarStops($south:Float!,$west:Float!,$north:Float!,$east:Float!){
stopPlacesByBbox(minimumLatitude:$south,minimumLongitude:$west,maximumLatitude:$north,maximumLongitude:$east,filterByInUse:false){
id name quays{id name latitude longitude lines{id publicCode name transportMode}}}}'''
DETAILS = '''query HamarLines($ids:[ID],$date:Date!){lines(ids:$ids){
id publicCode name transportMode authority{id name} journeyPatterns{
id name directionType pointsOnLink{points length distance}
quays{id name latitude longitude}
serviceJourneysForDate(date:$date){id}}}}'''

def encoded(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()

def inside_ring(lon, lat, ring):
    inside = False
    for a,b in zip(ring,ring[1:]+ring[:1]):
        if (a[1]>lat)!=(b[1]>lat) and lon < (b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0]:
            inside=not inside
    return inside

def in_boundary(lon,lat,geometry):
    polygons=geometry['coordinates'] if geometry['type']=='MultiPolygon' else [geometry['coordinates']]
    return any(inside_ring(lon,lat,polygon[0]) and not any(inside_ring(lon,lat,hole) for hole in polygon[1:]) for polygon in polygons)

def bbox(geometry):
    polygons=geometry['coordinates'] if geometry['type']=='MultiPolygon' else [geometry['coordinates']]
    points=[p for polygon in polygons for ring in polygon for p in ring]
    return {'south':min(p[1] for p in points)-.001,'west':min(p[0] for p in points)-.001,
            'north':max(p[1] for p in points)+.001,'east':max(p[0] for p in points)+.001}

def data_response(raw):
    doc=json.loads(raw)
    if doc.get('errors') or not isinstance(doc.get('data'),dict):
        raise ValueError('Entur returned errors or missing data; no complete catalogue can be claimed')
    return doc['data']

def discover(boundary, response):
    if boundary.get('kommunenummer')!='3403':raise ValueError('Expected Hamar municipality 3403')
    geometry=boundary['omrade']
    if geometry.get('type') not in ('Polygon','MultiPolygon'):raise ValueError('Unsupported boundary geometry')
    stops=response.get('stopPlacesByBbox')
    if not isinstance(stops,list) or len(stops)>5000:raise ValueError('Missing or oversized stop list')
    quays={}; lines={}
    for stop in stops:
        for quay in stop.get('quays') or []:
            lat,lon=quay.get('latitude'),quay.get('longitude')
            if not isinstance(lat,(float,int)) or not isinstance(lon,(float,int)):continue
            if not in_boundary(lon,lat,geometry):continue
            buses=[line for line in quay.get('lines') or [] if line.get('transportMode')=='bus']
            if not buses:continue
            quays[quay['id']]={'id':quay['id'],'name':quay['name'],'latitude':lat,'longitude':lon,'stop_place_id':stop['id']}
            for line in buses:
                if not re.fullmatch(r'[A-Za-z0-9_:.-]{1,120}',line['id']):raise ValueError('Invalid line identity')
                lines[line['id']]=line
    if not lines:raise ValueError('No Hamar bus services were discovered')
    if len(lines)>200:raise ValueError('Bus line request exceeds the 200-line acquisition limit')
    return lines,quays

def decode_geometry(text):
    if not isinstance(text,str) or len(text)>1_000_000:raise ValueError('Invalid encoded line geometry')
    result=[];values=[0,0];position=0
    while position<len(text):
        for axis in range(2):
            value=shift=0
            while True:
                if position>=len(text) or shift>30:raise ValueError('Malformed encoded line geometry')
                part=ord(text[position])-63;position+=1
                if not 0<=part<=63:raise ValueError('Malformed encoded line geometry')
                value|=(part&31)<<shift;shift+=5
                if part<32:break
            values[axis]+=~(value>>1) if value&1 else value>>1
        lat,lon=(v/1e5 for v in values)
        if not (-90<=lat<=90 and -180<=lon<=180):raise ValueError('Invalid geometry coordinates')
        result.append([lon,lat])
    return result

def build(boundary_raw, discovery_raw, details_raw, service_date, retrieved_at):
    date.fromisoformat(service_date)
    boundary=json.loads(boundary_raw)
    found,municipal_quays=discover(boundary,data_response(discovery_raw))
    returned=data_response(details_raw).get('lines')
    if not isinstance(returned,list):raise ValueError('Missing line details')
    ids=[line['id'] for line in returned]
    if len(ids)!=len(set(ids)) or set(ids)!=set(found):raise ValueError('Returned lines do not match discovered line identities')
    lines=[]
    for line in returned:
        if line.get('transportMode')!='bus':raise ValueError('Non-bus line in catalogue')
        patterns=[]
        for pattern in line.get('journeyPatterns') or []:
            stops=pattern.get('quays')
            if not isinstance(stops,list) or len(stops)<2:continue
            if not any(stop['id'] in municipal_quays for stop in stops):continue
            for stop in stops:
                if type(stop.get('latitude')) not in (int,float) or type(stop.get('longitude')) not in (int,float):
                    raise ValueError('Missing stop coordinates in an imported pattern')
            geometry=pattern.get('pointsOnLink')
            patterns.append({'id':pattern['id'],'name':pattern.get('name'),'direction':pattern.get('directionType'),
                'stops':[{**stop,'in_hamar':stop['id'] in municipal_quays} for stop in stops],
                'geometry':{'encoded_polyline':geometry['points'],'precision':5} if geometry and geometry.get('points') else None,
                'scheduled_journey_ids':[journey['id'] for journey in pattern['serviceJourneysForDate']]})
        lines.append({'id':line['id'],'code':line.get('publicCode') or line['id'],'name':line.get('name') or line['id'],
                      'authority':line.get('authority'),'patterns':patterns,'status':'imported' if patterns else 'pattern_data_unavailable'})
    lines.sort(key=lambda line:[int(t) if t.isdigit() else t.casefold() for t in re.split(r'(\d+)',line['code'])])
    return {'version':1,'id':'hamar-bus-catalogue','service_date':service_date,'retrieved_at':retrieved_at,
            'scope':{'name':'Hamar municipality','municipality_code':'3403','boundary_source':BOUNDARY,
                     'selection':'Bus lines reported by Entur at quays whose coordinates lie within the saved official municipal polygon.',
                     'external_completeness_verified':False},
            'attribution':'Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av Entur AS. Kommunegrense: Kartverket.',
            'source_url':'https://developer.entur.no/open-data/timetable','licence_url':'https://data.norge.no/nlod/no/2.0',
            'hamar_quays':list(sorted(municipal_quays.values(),key=lambda stop:stop['id'])),'lines':lines}

def fetch(url,body=None,opener=urllib.request.urlopen):
    request=urllib.request.Request(url,data=json.dumps(body).encode() if body else None,
        headers={'Content-Type':'application/json','ET-Client-Name':CLIENT,'User-Agent':'HamarAccessLab/1.0'})
    with opener(request,timeout=TIMEOUT) as response:
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('Acquisition exceeded the 16 MiB per-response limit')
    return raw

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Make exactly three bounded official-source requests')
    parser.add_argument('--date',default=date.today().isoformat())
    parser.add_argument('--directory',type=Path,default=ROOT/'fixtures'/'transit'/'hamar')
    parser.add_argument('--output',type=Path,help='Replay raw sources to this file, with zero network calls')
    args=parser.parse_args();date.fromisoformat(args.date)
    directory=args.directory
    if args.live:
        if args.output:parser.error('--output is for offline replay')
        if (directory/'manifest.json').exists():parser.error('Use a fresh directory; existing acquisitions are not overwritten')
        boundary=fetch(BOUNDARY);bounds=bbox(json.loads(boundary)['omrade'])
        discovery=fetch(ENDPOINT,{'query':DISCOVER,'variables':bounds})
        found,_=discover(json.loads(boundary),data_response(discovery))
        variables={'ids':sorted(found),'date':args.date}
        details=fetch(ENDPOINT,{'query':DETAILS,'variables':variables})
        retrieved=datetime.now(timezone.utc).isoformat()
        result=build(boundary,discovery,details,args.date,retrieved)
        directory.mkdir(parents=True,exist_ok=True)
        records={'boundary.json':boundary,'discovery.json':discovery,'line-details.json':details}
        manifest={'service_date':args.date,'retrieved_at':retrieved,'requests':[{'url':BOUNDARY},{'url':ENDPOINT,'query':DISCOVER,'variables':bounds},{'url':ENDPOINT,'query':DETAILS,'variables':variables}],
                  'sha256':{name:hashlib.sha256(raw).hexdigest() for name,raw in records.items()}}
        for name,raw in records.items():(directory/name).write_bytes(raw)
        (directory/'manifest.json').write_bytes(encoded(manifest))
    else:
        if not args.output:parser.error('Choose --live or --output for offline replay')
        manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
        records={name:(directory/name).read_bytes() for name in ('boundary.json','discovery.json','line-details.json')}
        if any(hashlib.sha256(raw).hexdigest()!=manifest['sha256'][name] for name,raw in records.items()):raise ValueError('Saved source hash mismatch')
        result=build(records['boundary.json'],records['discovery.json'],records['line-details.json'],manifest['service_date'],manifest['retrieved_at'])
    (args.output or directory/'catalogue.json').write_bytes(encoded(result))
    print(json.dumps({'lines':len(result['lines']),'patterns':sum(len(line['patterns']) for line in result['lines']),
        'hamar_quays':len(result['hamar_quays']),'service_date':result['service_date'],'requests':3 if args.live else 0}))

if __name__=='__main__':main()
