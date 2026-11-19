"""Read the saved municipal bus inventory; never make runtime network calls."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
try:
    from .import_hamar_bus import build, decode_geometry, encoded
except ImportError:
    from import_hamar_bus import build, decode_geometry, encoded

@lru_cache(maxsize=2)
def load(root):
    directory=Path(root)/'fixtures'/'transit'/'hamar'
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    sources={name:(directory/name).read_bytes() for name in ('boundary.json','discovery.json','line-details.json')}
    for name,raw in sources.items():
        if hashlib.sha256(raw).hexdigest()!=manifest['sha256'][name]:raise ValueError('Bus source checksum mismatch')
    catalogue=build(sources['boundary.json'],sources['discovery.json'],sources['line-details.json'],manifest['service_date'],manifest['retrieved_at'])
    if encoded(catalogue)!=(directory/'catalogue.json').read_bytes():raise ValueError('Bus catalogue differs from its source replay')
    return catalogue

def query(root,line_id=None,pattern_id=None):
    catalogue=load(str(root))
    source={key:catalogue[key] for key in ('id','service_date','retrieved_at','scope','attribution','source_url','licence_url')}
    if line_id is None:
        return {**source,'line_count':len(catalogue['lines']),'hamar_quay_count':len(catalogue['hamar_quays']),
            'lines':[{key:line[key] for key in ('id','code','name','authority','status')} |
                {'pattern_count':len(line['patterns'])} for line in catalogue['lines']]}
    line=next((line for line in catalogue['lines'] if line['id']==line_id),None)
    if line is None:raise LookupError('Unknown imported bus line')
    if pattern_id is None:
        return {**source,'line':{key:line[key] for key in ('id','code','name','authority','status')},
            'patterns':[{'id':p['id'],'name':p['name'],'direction':p['direction'],'stop_count':len(p['stops']),
                         'first_stop':p['stops'][0]['name'],'last_stop':p['stops'][-1]['name'],
                         'scheduled_journey_count':len(p['scheduled_journey_ids'])} for p in sorted(line['patterns'],key=lambda item:(-len(item['scheduled_journey_ids']),item['id']))]}
    pattern=next((p for p in line['patterns'] if p['id']==pattern_id),None)
    if pattern is None:raise LookupError('Unknown imported route variant')
    geometry=decode_geometry(pattern['geometry']['encoded_polyline']) if pattern['geometry'] else None
    return {**source,'line':{key:line[key] for key in ('id','code','name','authority','status')},
            'pattern':{**pattern,'geometry':geometry,'scheduled_journey_count':len(pattern['scheduled_journey_ids'])}}
