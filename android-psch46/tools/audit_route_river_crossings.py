#!/usr/bin/env python3
import json, math, time
from collections import defaultdict
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'app'/'src'/'main'/'assets'/'www'/'data.js'
PREFIX='window.OFFLINE_DATA='
S=requests.Session(); S.headers.update({'User-Agent':'PSCH46-route-river-audit/2.1'})
OVERPASS=['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']
CELL=.02

def hav(a,b):
    lat1,lon1=map(math.radians,a); lat2,lon2=map(math.radians,b)
    dlat=lat2-lat1; dlon=lon2-lon1
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(h)))

def overpass(q,label):
    last=None
    for ep in OVERPASS:
        for attempt in range(4):
            try:
                print('Overpass',label,ep,'attempt',attempt+1)
                r=S.post(ep,data={'data':q},timeout=300); r.raise_for_status(); d=r.json()
                print(' ',len(d.get('elements',[])),'elements'); return d
            except Exception as e:
                last=e; print(' failed',repr(e)); time.sleep(3+attempt*4)
    raise RuntimeError(f'Overpass failed {label}: {last}')

def orient(a,b,c): return (b[1]-a[1])*(c[0]-a[0])-(b[0]-a[0])*(c[1]-a[1])
def intersect(a,b,c,d):
    o1,o2,o3,o4=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
    eps=1e-12
    if (o1>eps and o2>eps) or (o1<-eps and o2<-eps) or (o3>eps and o4>eps) or (o3<-eps and o4<-eps): return None
    x1,y1=a[1],a[0]; x2,y2=b[1],b[0]; x3,y3=c[1],c[0]; x4,y4=d[1],d[0]
    den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    if abs(den)<1e-14:
        return min([a,b,c,d],key=lambda p:min(hav(p,a),hav(p,b))+min(hav(p,c),hav(p,d)))
    px=((x1*y2-y1*x2)*(x3-x4)-(x1-x2)*(x3*y4-y3*x4))/den
    py=((x1*y2-y1*x2)*(y3-y4)-(y1-y2)*(x3*y4-y3*x4))/den
    return (py,px)

def point_seg_km(p,a,b):
    lat0=math.radians(p[0]); kx=111.320*math.cos(lat0); ky=110.574
    px,py=p[1]*kx,p[0]*ky; ax,ay=a[1]*kx,a[0]*ky; bx,by=b[1]*kx,b[0]*ky
    dx,dy=bx-ax,by-ay
    if dx==0 and dy==0:return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx),py-(ay+t*dy))

def cells_for(a,b):
    la0,la1=sorted((a[0],b[0])); lo0,lo1=sorted((a[1],b[1]))
    ia0,ia1=math.floor(la0/CELL),math.floor(la1/CELL); io0,io1=math.floor(lo0/CELL),math.floor(lo1/CELL)
    for ia in range(ia0,ia1+1):
        for io in range(io0,io1+1): yield ia,io

def segs(elements,predicate=lambda tags:True):
    out=[]
    for e in elements:
        tags=e.get('tags') or {}
        if not predicate(tags):continue
        pts=[(float(p['lat']),float(p['lon'])) for p in (e.get('geometry') or []) if 'lat' in p and 'lon' in p]
        for a,b in zip(pts,pts[1:]):out.append((a,b,tags))
    return out

raw=DATA.read_text(encoding='utf-8').strip(); body=raw[len(PREFIX):]
if body.endswith(';'):body=body[:-1]
data=json.loads(body)
rel=overpass('[out:json][timeout:90];rel["boundary"="administrative"]["name"="Рамешковский муниципальный округ"];out ids;','district')
rels=[e for e in rel.get('elements',[]) if e.get('type')=='relation']
if not rels:raise RuntimeError('District relation not found')
AREA=int(rels[0]['id'])+3600000000
rivers=overpass(f'''[out:json][timeout:240];area({AREA})->.a;way["waterway"="river"](area.a);out geom tags;''','rivers')
bridges=overpass(f'''[out:json][timeout:240];area({AREA})->.a;way["highway"]["bridge"](area.a);out geom tags;''','road bridges')
river_segs=segs(rivers.get('elements',[])); bridge_segs=segs(bridges.get('elements',[]),lambda t:(t.get('bridge') or '').lower() not in {'no','false','0'})
print('River segments:',len(river_segs),'bridge segments:',len(bridge_segs))
ri=defaultdict(list); bi=defaultdict(list)
for s in river_segs:
    for cell in cells_for(s[0],s[1]):ri[cell].append(s)
for s in bridge_segs:
    for cell in cells_for(s[0],s[1]):bi[cell].append(s)

def bridge_near(p):
    ia,io=math.floor(p[0]/CELL),math.floor(p[1]/CELL); cand=[]
    for da in (-1,0,1):
        for do in (-1,0,1):cand.extend(bi.get((ia+da,io+do),[]))
    return min((point_seg_km(p,s[0],s[1]) for s in cand),default=999)<0.14

def unbridged_crossings(a,b):
    cand=[]
    for cell in cells_for(a,b):cand.extend(ri.get(cell,[]))
    bad=[]; used=set(); total=0
    for rs in cand:
        k=(rs[0],rs[1])
        if k in used:continue
        used.add(k)
        p=intersect(a,b,rs[0],rs[1])
        if p is None:continue
        total+=1
        if not bridge_near(p):bad.append((round(p[0],6),round(p[1],6)))
    return bad,total

bad=[]; crossing_count=0; connector_crossings=0; checked=0
points=list(data.get('settlements',[]))+list(data.get('extraPlaces',[]))
for s in points:
    if s.get('routeVerified') is not True:continue
    route=s.get('route') or []
    if len(route)<2:continue
    seen=[]
    for a,b in zip(route,route[1:]):
        badd,n=unbridged_crossings(tuple(a),tuple(b)); crossing_count+=n; seen.extend(('road',x) for x in badd)
    # The route itself ends on a reachable road. Check whether the settlement marker is across a river
    # from that road endpoint; this catches a tempting wrong-bank snap even though no off-road line is drawn.
    endpoint=tuple(route[-1]); target=(float(s['lat']),float(s['lon']))
    if hav(endpoint,target)>0.03:
        badd,n=unbridged_crossings(endpoint,target); connector_crossings+=n; seen.extend(('endpoint',x) for x in badd)
    if seen:bad.append({'name':s.get('name'),'official':bool(s.get('isOfficial')),'snapKm':s.get('routeSnapKm'),'crossings':seen[:5]})
    checked+=1
if bad:
    print('ROUTES / ENDPOINT SNAPS WITH UNBRIDGED RIVER CROSSINGS:')
    for x in bad[:50]:print(' -',x)
    official_bad=[x for x in bad if x['official']]
    if official_bad:raise RuntimeError(f'{len(official_bad)} official routes end/cross on the wrong side of a mapped river')
    # Extra map localities are not canonical settlements; mark their reward route unverified instead of failing the APK.
    bad_names={x['name'] for x in bad}
    for s in data.get('extraPlaces',[]):
        if s.get('name') in bad_names:s['routeVerified']=False
meta=data.setdefault('meta',{})
meta['riverCrossingAudit']=True; meta['riverCrossingsChecked']=crossing_count; meta['endpointRiverCrossingsChecked']=connector_crossings; meta['riverAuditRoutes']=checked
DATA.write_text(PREFIX+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print('River crossing audit passed. Routes:',checked,'road intersections:',crossing_count,'endpoint intersections:',connector_crossings)
