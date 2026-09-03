#!/usr/bin/env python3
import json, math, heapq, re, time
from collections import defaultdict
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "src" / "main" / "assets" / "www" / "data.js"
PREFIX = "window.OFFLINE_DATA="
UA = "PSCH46-Rameshki-Firetruck-Safe-Router/2.1"
S = requests.Session(); S.headers.update({"User-Agent": UA})
OVERPASS = ["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]

# Actual training vehicle profile supplied for PSCH-46.
TRUCK = {"mass_t":20.0,"width_m":2.7,"height_m":2.8,"length_m":9.0}


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("ё","е").replace("Ё","Е").strip().lower())

def hav(a,b):
    lat1,lon1=map(math.radians,a); lat2,lon2=map(math.radians,b)
    dlat=lat2-lat1; dlon=lon2-lon1
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(h)))

def rdp(points, eps=0.000055):
    if len(points)<=2: return points
    x1,y1=points[0]; x2,y2=points[-1]; den=math.hypot(x2-x1,y2-y1)
    best=-1; bi=0
    for i,(x,y) in enumerate(points[1:-1],1):
        d=math.hypot(x-x1,y-y1) if den==0 else abs((y2-y1)*x-(x2-x1)*y+x2*y1-y2*x1)/den
        if d>best: best=d; bi=i
    if best>eps:
        a=rdp(points[:bi+1],eps); b=rdp(points[bi:],eps); return a[:-1]+b
    return [points[0],points[-1]]

def overpass(q,label):
    last=None
    for ep in OVERPASS:
        for attempt in range(4):
            try:
                print("Overpass",label,ep,"attempt",attempt+1)
                r=S.post(ep,data={"data":q},timeout=300); r.raise_for_status(); d=r.json()
                print(" ",len(d.get("elements",[])),"elements"); return d
            except Exception as e:
                last=e; print(" failed",repr(e)); time.sleep(3+attempt*4)
    raise RuntimeError(f"Overpass failed for {label}: {last}")

def num_tag(v):
    if not v: return None
    m=re.search(r"\d+(?:[.,]\d+)?",str(v).replace(",","."))
    return float(m.group()) if m else None

def restricted(tags):
    deny={"no","private"}
    for k in ("access","vehicle","motor_vehicle","motorcar","hgv"):
        if norm(tags.get(k)) in deny: return True, f"{k}={tags.get(k)}"
    if norm(tags.get("ford")) in {"yes","true","1"} or norm(tags.get("highway"))=="ford": return True,"ford"
    if norm(tags.get("seasonal")) in {"yes","true","1"}: return True,"seasonal"
    sm=norm(tags.get("smoothness"))
    if sm in {"horrible","very_horrible","impassable"}: return True,"smoothness="+sm
    mw=num_tag(tags.get("maxweight")); mh=num_tag(tags.get("maxheight")); mwi=num_tag(tags.get("maxwidth")); ml=num_tag(tags.get("maxlength"))
    if mw is not None and mw<TRUCK["mass_t"]: return True,f"maxweight={mw}"
    if mh is not None and mh<TRUCK["height_m"]: return True,f"maxheight={mh}"
    if mwi is not None and mwi<TRUCK["width_m"]: return True,f"maxwidth={mwi}"
    if ml is not None and ml<TRUCK["length_m"]: return True,f"maxlength={ml}"
    return False,""

def factor(tags):
    h=norm(tags.get("highway"))
    base={"trunk":1.0,"primary":1.0,"secondary":1.03,"tertiary":1.08,"unclassified":1.18,"residential":1.34,"living_street":1.42,"service":2.4,"track":3.0}.get(h,1.5)
    if h=="service" and norm(tags.get("service")) in {"driveway","parking_aisle","alley"}: base*=2.2
    if h=="track":
        base*= {"grade1":1.0,"grade2":1.25,"grade3":1.8,"grade4":3.2,"grade5":5.0}.get(norm(tags.get("tracktype")),1.5)
    surf=norm(tags.get("surface"))
    base*= {"asphalt":1.0,"concrete":1.03,"concrete:plates":1.08,"paving_stones":1.15,"compacted":1.35,"fine_gravel":1.55,"gravel":1.8,"unpaved":2.0,"ground":2.7,"dirt":3.0,"earth":3.0,"sand":5.0,"mud":7.0}.get(surf,1.0)
    sm=norm(tags.get("smoothness"))
    base*= {"excellent":.98,"good":1.0,"intermediate":1.05,"bad":1.4,"very_bad":2.2}.get(sm,1.0)
    return base

def point_seg_dist_km(p,a,b):
    # Local equirectangular projection, good enough at district scale.
    lat0=math.radians(p[0]); kx=111.320*math.cos(lat0); ky=110.574
    px,py=p[1]*kx,p[0]*ky; ax,ay=a[1]*kx,a[0]*ky; bx,by=b[1]*kx,b[0]*ky
    dx,dy=bx-ax,by-ay
    if dx==0 and dy==0: return math.hypot(px-ax,py-ay),0.0
    t=max(0.0,min(1.0,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    qx,qy=ax+t*dx,ay+t*dy
    return math.hypot(px-qx,py-qy),t

def route_via(route, official, target_id, total_km):
    if len(route)<2: return []
    seglens=[hav(tuple(a),tuple(b)) for a,b in zip(route,route[1:])]
    cum=[0.0]
    for d in seglens: cum.append(cum[-1]+d)
    out=[]
    for s in official:
        if s.get("id")==target_id or norm(s.get("name"))=="рамешки": continue
        p=(float(s["lat"]),float(s["lon"])); best=(1e9,0.0)
        for i,(a,b) in enumerate(zip(route,route[1:])):
            d,t=point_seg_dist_km(p,tuple(a),tuple(b))
            if d<best[0]: best=(d,cum[i]+seglens[i]*t)
        # 700 m catches villages lying just off the through-road but avoids nearby parallel settlements.
        if best[0] <= 0.70 and best[1] >= 0.8 and best[1] <= max(0,total_km-0.35):
            out.append({"id":s.get("id"),"name":s["name"],"lat":s["lat"],"lon":s["lon"],"km":round(best[1],1),"offsetKm":round(best[0],2)})
    out.sort(key=lambda x:x["km"])
    # De-duplicate same-name close points.
    ded=[]
    for x in out:
        if ded and norm(ded[-1]["name"])==norm(x["name"]) and abs(ded[-1]["km"]-x["km"])<1.0: continue
        ded.append(x)
    return ded

raw=DATA.read_text(encoding="utf-8").strip(); body=raw[len(PREFIX):]
if body.endswith(";"): body=body[:-1]
data=json.loads(body)

rel=overpass('[out:json][timeout:90];rel["boundary"="administrative"]["name"="Рамешковский муниципальный округ"];out ids tags;','district relation')
rels=[e for e in rel.get('elements',[]) if e.get('type')=='relation']
if not rels: raise RuntimeError('District relation not found')
RID=int(rels[0]['id']); AREA=RID+3600000000

road_q=f'''[out:json][timeout:300][maxsize:1073741824];area({AREA})->.a;way["highway"~"trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|track"](area.a);out geom tags;'''
ford_q=f'''[out:json][timeout:180];area({AREA})->.a;(node["ford"](area.a);node["highway"="ford"](area.a);way["ford"](area.a);way["highway"="ford"](area.a););out center geom tags;'''
roads_raw=overpass(road_q,'safe roads'); fords_raw=overpass(ford_q,'fords')
ford_pts=[]
for e in fords_raw.get('elements',[]):
    if 'lat' in e and 'lon' in e: ford_pts.append((float(e['lat']),float(e['lon'])))
    for p in e.get('geometry') or []:
        if 'lat' in p and 'lon' in p: ford_pts.append((float(p['lat']),float(p['lon'])))
print('Known ford coordinates:',len(ford_pts))

def near_ford(p): return any(hav(p,f)<0.035 for f in ford_pts)

g=defaultdict(list); all_nodes=set(); excluded=defaultdict(int); accepted=0
for e in roads_raw.get('elements',[]):
    tags=e.get('tags') or {}; bad,why=restricted(tags)
    if bad: excluded[why]+=1; continue
    geom=e.get('geometry') or []
    pts=[(round(float(p['lat']),6),round(float(p['lon']),6)) for p in geom if 'lat' in p and 'lon' in p]
    if len(pts)<2: continue
    f=factor(tags); oneway=norm(tags.get('oneway')) in {'yes','true','1'}
    for a,b in zip(pts,pts[1:]):
        if near_ford(a) or near_ford(b): excluded['ford-node-edge']+=1; continue
        d=hav(a,b); w=d*f
        g[a].append((b,w,d)); all_nodes.add(a); all_nodes.add(b)
        if not oneway: g[b].append((a,w,d))
    accepted+=1
print('Accepted road ways:',accepted,'excluded:',dict(excluded),'graph nodes:',len(all_nodes))
if not g: raise RuntimeError('Safe graph empty')

nodes=list(all_nodes)
def nearest(pt):
    c=math.cos(math.radians(pt[0])); return min(nodes,key=lambda n:(n[0]-pt[0])**2+((n[1]-pt[1])*c)**2)
start=nearest((data['station']['lat'],data['station']['lon']))
dist={start:0.0}; real={start:0.0}; prev={}; pq=[(0.0,start)]
while pq:
    d,u=heapq.heappop(pq)
    if d!=dist.get(u): continue
    for v,w,rd in g[u]:
        nd=d+w
        if nd<dist.get(v,float('inf')):
            dist[v]=nd; real[v]=real[u]+rd; prev[v]=u; heapq.heappush(pq,(nd,v))

def route_to(pt):
    t=nearest(pt)
    if t not in dist: return [],None
    p=[t]; cur=t; guard=0
    while cur!=start and cur in prev and guard<250000:
        cur=prev[cur]; p.append(cur); guard+=1
    if p[-1]!=start: return [],None
    p.reverse(); path=[[x[0],x[1]] for x in p]
    # Very light simplification: preserve real road bends instead of drawing shortcuts.
    path=rdp(path,0.000055)
    return [[round(a,6),round(b,6)] for a,b in path],round(real[t],1)

allp=list(data.get('settlements',[]))+list(data.get('extraPlaces',[]))
official=list(data.get('settlements',[])); failures=[]
for i,s in enumerate(allp,1):
    r,km=route_to((float(s['lat']),float(s['lon'])))
    if not r:
        failures.append(s['name']); continue
    s['route']=r; s['distanceKm']=km; s['via']=route_via(r,official,s.get('id'),km or 0)
    if i%50==0: print('Safe routes',i,'/',len(allp))
if failures:
    print('UNROUTABLE:',failures[:30]); raise RuntimeError(f'{len(failures)} training points have no safe road route')

byid={s.get('id'):s for s in allp}
for group in ('centers','dpk'):
    for s in data.get(group,[]):
        src=byid.get(s.get('id'))
        if src:
            s['route']=src.get('route',[]); s['distanceKm']=src.get('distanceKm'); s['via']=src.get('via',[])

meta=data.setdefault('meta',{})
meta.update({
    'routingProfile':'firetruck-safe-v2.1',
    'truckProfile':TRUCK,
    'knownFordCoordinates':len(ford_pts),
    'routeGeometryEpsilon':0.000055,
    'safeRoutes':len(allp),
    'routesWithVia':sum(1 for s in allp if s.get('via')),
    'routeValidation':True
})
DATA.write_text(PREFIX+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print('Safe routing complete:',meta)
