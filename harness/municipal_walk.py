"""Municipality-wide walking graph from a sanitized, saved OSM source.

Existing historical assessment cases remain separate. No joins are invented
between geometrically close roads: connectivity follows shared OSM node IDs.
"""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

CASE_ID = "hamar-municipality"
FILE = "hamar-municipality.json"
HIGHWAYS = {"residential", "living_street", "unclassified", "service", "road",
            "primary", "primary_link", "secondary", "secondary_link", "tertiary",
            "tertiary_link", "trunk", "trunk_link", "footway", "path", "pedestrian",
            "cycleway", "track", "steps", "bridleway"}
EXPLICIT = {"yes", "designated", "permissive"}
LABEL = "Hamar municipality · streets and walking paths"
SUMMARY = "Mapped public walking connections across Hamar municipality. Choose your own start and destination; no closure is applied automatically."


def allowed(tags):
    if tags.get("highway") not in HIGHWAYS or tags.get("motorroad") == "yes":
        return False
    foot = tags.get("foot")
    if foot is not None and foot not in EXPLICIT:
        return False
    if tags.get("foot:conditional") or (tags.get("access:conditional") and foot not in EXPLICIT):
        return False
    return foot in EXPLICIT or tags.get("access") not in {"no", "private", "destination", "customers", "delivery", "permit", "agricultural", "forestry"}


def blocked_node(tags):
    return (tags.get("foot") in {"no", "private"}
            or (tags.get("access") in {"no", "private"} and tags.get("foot") not in EXPLICIT)
            or tags.get("barrier") in {"wall", "fence", "hedge", "retaining_wall"})


def metres(a, b):
    return math.hypot((a[0]-b[0])*111320,
                      (a[1]-b[1])*111320*math.cos(math.radians((a[0]+b[0])/2)))


def streets(data):
    nodes = {e["id"]: e for e in data["elements"] if e["type"] == "node"}
    groups = {}
    for way in data["elements"]:
        if way["type"] != "way" or not way.get("tags", {}).get("name"):
            continue
        name = way["tags"]["name"]
        group = groups.setdefault(name, [])
        if len(way["nodes"]) > 1:
            group.append(way)
    result = []
    for name, ways in sorted(groups.items()):
        usable = [way for way in ways if allowed(way["tags"])]
        way = max(usable or ways, key=lambda w: len(w["nodes"]))
        point = nodes[way["nodes"][len(way["nodes"])//2]]
        result.append({"id": "osm-street-"+str(way["id"]), "name": name,
                       "kind": "street", "coordinates": [point["lat"], point["lon"]],
                       "walkable": bool(usable), "way_count": len(ways),
                       "source_id": "hamar-municipal-streets",
                       "source": {"provider": "OpenStreetMap", "attribution": "© OpenStreetMap contributors",
                                  "licence_url": data["licence_url"], "source_url": "https://www.openstreetmap.org/way/"+str(way["id"]),
                                  "retrieved_at_utc": data["retrieved_at"]}})
    return result


def load_case(root):
    root = Path(root)
    raw = (root/"fixtures/maps"/FILE).read_bytes()
    expected = json.loads((root/"fixtures/maps/manifest.json").read_text(encoding="utf-8"))["fixtures"][FILE]
    if hashlib.sha256(raw).hexdigest() != expected["sanitized_fixture_sha256"]:
        raise ValueError("Municipal map checksum mismatch")
    data = json.loads(raw)
    if data["area"]["ref"] != "3403":
        raise ValueError("Municipal map must cover Hamar")
    boundary_raw = (root/"fixtures/transit/hamar/boundary.json").read_bytes()
    if hashlib.sha256(boundary_raw).hexdigest() != expected["boundary_sha256"]:
        raise ValueError("Municipal boundary checksum mismatch")
    boundary = json.loads(boundary_raw)["omrade"]
    points = {str(e["id"]): [e["lat"],e["lon"]] for e in data["elements"] if e["type"] == "node"}
    blocked = {str(e["id"]) for e in data["elements"] if e["type"] == "node" and blocked_node(e.get("tags",{}))}
    network, counts = [], Counter()
    for way in data["elements"]:
        if way["type"] != "way":
            continue
        tags = way.get("tags",{})
        if not allowed(tags):
            counts["excluded_ways"] += 1
            continue
        counts["walking_ways"] += 1
        for index, (a,b) in enumerate(zip(way["nodes"], way["nodes"][1:]), 1):
            a,b = str(a),str(b)
            if a not in points or b not in points:
                raise ValueError("Municipal way references a missing node")
            if a in blocked or b in blocked:
                counts["blocked_links"] += 1
                continue
            length = metres(points[a],points[b])
            if round(length) < 1:
                continue
            # Add vertices along long edges, so a house beside a long rural
            # road is not rejected merely because OSM vertices are far apart.
            parts = max(1, math.ceil(length/50))
            refs = [a]
            for part in range(1,parts):
                node_id = f"m-{way['id']}-{index}-{part}"
                fraction = part/parts
                points[node_id] = [points[a][axis]+fraction*(points[b][axis]-points[a][axis]) for axis in (0,1)]
                refs.append(node_id)
            refs.append(b)
            total = max(parts,round(length))
            for part,(start,end) in enumerate(zip(refs,refs[1:]),1):
                if tags.get("oneway:foot") == "-1":
                    start,end = end,start
                network.append({"id": f"osm-way-{way['id']}-segment-{index}-{part}",
                                "from":start,"to":end,"metres":total//parts+(part<=total%parts),
                                "modes":["walking"],"source":f"https://www.openstreetmap.org/way/{way['id']}",
                                "walking_oneway":tags.get("oneway:foot") in {"yes","1","-1"}})
    used = {node for link in network for node in (link["from"],link["to"])}
    points = {key:value for key,value in points.items() if key in used}
    if not points or not network:
        raise ValueError("Municipal walking graph is empty")
    def nearest(point):
        return min(points,key=lambda node:metres(point,points[node]))
    origin,destination = nearest([60.794984,11.072413]),nearest([60.7916,11.0825])
    journey={"id":"municipal-centre-example","label":"Seminargata to Hamar station",
             "origin":{"id":origin,"label":"Seminargata","coordinates":points[origin]},
             "destination":{"id":destination,"label":"Hamar station","coordinates":points[destination]},
             "baseline_metres":None,"evidence":{}}
    # Component counts expose genuine map gaps instead of inventing connectors.
    adjacent={key:[] for key in points}
    for link in network:
        adjacent[link["from"]].append(link["to"]);adjacent[link["to"]].append(link["from"])
    unseen=set(points);sizes=[]
    while unseen:
        pending=[unseen.pop()];size=0
        while pending:
            node=pending.pop();size+=1
            for other in adjacent[node]:
                if other in unseen:unseen.remove(other);pending.append(other)
        sizes.append(size)
    counts.update({"nodes":len(points),"links":len(network),"components":len(sizes),"largest_component_nodes":max(sizes)})
    return {"id":CASE_ID,"municipal":True,"mode":"walking",
            "config":{"label":LABEL,"summary":SUMMARY,"osm":FILE},
            "scenario":{"metadata":{"id":CASE_ID},"network":network,
                        "journeys":[{"id":journey["id"],"origin":origin,"destination":destination}]},
            "links":{link["id"]:link for link in network},"nodes":points,
            "coverage":{"minlat":min(p[0] for p in points.values()),"maxlat":max(p[0] for p in points.values()),
                        "minlon":min(p[1] for p in points.values()),"maxlon":max(p[1] for p in points.values()),
                        "walking_node_count":len(points),"walking_link_count":len(network),"walking_way_count":counts["walking_ways"],"municipality":"3403"},
            "boundary":boundary,"statistics":dict(counts),"candidates":{},"sections":[],"section_ids":{},
            "journeys":[journey],"journey_ids":{journey["id"]},"manifest":expected,
            "attribution":"© OpenStreetMap contributors","license":"ODbL 1.0"}


def no_change_assessment(scenario, when, shortest):
    """Normal walking is a valid run without inventing a closure project."""
    rows=[]
    for journey in scenario["journeys"]:
        route=shortest(scenario["network"],journey["origin"],journey["destination"])
        rows.append({"journey_id":journey["id"],"baseline":route,"route":route,"change_metres":0,
                     "status":"unchanged","contributing_projects":[],"individual_projects":{},"overlap_effect":False})
    return {"comparison":{"alternatives":[{"journeys":rows}]},
            "project_assessment":{"assessment_date":when,"hypothetical":False,"date_rule":"No closure projects configured.","active_projects":[],"inactive_projects":[]}}
