#!/usr/bin/env python3
import json, math, re, time
from collections import defaultdict
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'app'/'src'/'main'/'assets'/'www'/'data.js'
PREFIX='window.OFFLINE_DATA='
AREA=3600570645
TRUCK={'mass_t':20.0,'width_m':2.7,'height_m':2.8,'length_m':9.0}
S=requests.Session();S.headers.update({'User-Agent':'PSCH46-route-audit-fast/2.2'})
OVERPASS=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter']
CELL=.02

def norm(s):return re.sub(r'\s+',' ',str(s or '').replace('ё','е').replace('Ё','Е').strip().lower())
def hav(a,b):
    la1,lo1=map(math.radians,a);la2,lo2=map(math.radians,b);dla=la2-la1;dlo=lo2-lo1
    h=math.sin(dla/2)**2+math.cos(la1)*math.cos(la2)*math.sin(dlo/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(h)))
def num(v):
    m=re.search(r'\d+(?:[.,]\d+)?',str(v or '').replace(',','.'));return float(m.group()) if m else None
def pseg(p,a,b):
    lat0=math.radians(p[0]);kx=111.320*math.cos(lat0);ky=110.574
    px,py=p[1]*kx,p[0]*ky;ax,ay=a[1]*kx,a[0]*ky;bx,by=b[1]*kx,b[0]*ky;dx,dy=bx-ax,by-ay
    if dx==0 and dy==0:return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)));return math.hypot(px-(ax+t*dx),py-(ay+t*dy))
def orient(a,b,c):return (b[1]-a[1])*(c[0]-a[0])-(b[0]-a[0])*(c[1]-a[1])
def intersect(a,b,c,d):
    o1,o2,o3,o4=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b);eps=1e-12
    if (o1>eps and o2>eps) or (o1<-eps and o2<-eps) or (o3>eps and o4>eps) or (o3<-eps and o4<-eps):return None
    x1,y1=a[1],a[0];x2,y2=b[1],b[0];x3,y3=c[1],c[0];x4,y4=d[1],d[0]
    den=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    if abs(den)<1e-14:return None
    px=((x1*y2-y1*x2)*(x3-x4)-(x1-x2)*(x3*y4-y3*x4))/den
    py=((x1*y2-y1*x2)*(y3-y4)-(y1-y2)*(x3*y4-y3*x4))/den
    return (py,px)
def cells(a,b):
    for ia in range(math.floor(min(a[0],b[0])/CELL),math.floor(max(a[0],b[0])/CELL)+1):
      for io in range(math.floor(min(a[1],b[1])/CELL),math.floor(max(a[1],b[1])/CELL)+1):yield ia,io
def overpass(q):
    last=None
    for ep in OVERPASS:
      try:
        print('Audit query',ep);r=S.post(ep,data={'data':q},timeout=150);r.raise_for_status();d=r.json();print('elements',len(d.get('elements',[])));return d
      except Exception as e:last=e;print(' failed',repr(e));time.sleep(2)
    raise RuntimeError(f'audit Overpass failed: {last}')
def geom(e):return [(float(p['lat']),float(p['lon'])) for p in (e.get('geometry') or []) if 'lat'in p and 'lon'in p]
def restriction_reason(tags):
    for k in ('access','vehicle','motor_vehicle','motorcar'):
      if norm(tags.get(k))=='no':return k+'=no'
    if norm(tags.get('smoothness'))=='impassable':return 'непроезжая дорога'
    vals=[('maxweight','масса',TRUCK['mass_t']),('maxheight','высота',TRUCK['height_m']),('maxwidth','ширина',TRUCK['width_m']),('maxlength','длина',TRUCK['length_m'])]
    for k,label,need in vals:
      v=num(tags.get(k))
      if v is not None and v<need:return f'{label}: ограничение {v}'
    return None

def route_via(route,official,target_id):
    if len(route)<2:return []
    seglen=[hav(tuple(a),tuple(b)) for a,b in zip(route,route[1:])];cum=[0]
    for d in seglen:cum.append(cum[-1]+d)
    out=[]
    for s in official:
      if s.get('id')==target_id or norm(s.get('name'))=='рамешки':continue
      p=(float(s['lat']),float(s['lon']));best=(999,0)
      for i,(a,b) in enumerate(zip(route,route[1:])):
        d=pseg(p,tuple(a),tuple(b))
        if d<best[0]:best=(d,cum[i]+seglen[i]/2)
      if best[0]<=.70 and best[1]>=.8 and best[1]<=max(0,cum[-1]-.35):out.append({'id':s.get('id'),'name':s['name'],'lat':s['lat'],'lon':s['lon'],'km':round(best[1],1),'offsetKm':round(best[0],2)})
    out.sort(key=lambda x:x['km']);return out

raw=DATA.read_text(encoding='utf-8').strip();body=raw[len(PREFIX):];body=body[:-1] if body.endswith(';') else body;data=json.loads(body)
q=f'''[out:json][timeout:150][maxsize:536870912];area({AREA})->.a;(
 node["ford"](area.a);node["highway"="ford"](area.a);way["ford"](area.a);way["highway"="ford"](area.a);
 way["waterway"="river"](area.a);way["highway"]["bridge"](area.a);
 way["highway"]["maxweight"](area.a);way["highway"]["maxheight"](area.a);way["highway"]["maxwidth"](area.a);way["highway"]["maxlength"](area.a);
 way["highway"]["access"="no"](area.a);way["highway"]["vehicle"="no"](area.a);way["highway"]["motor_vehicle"="no"](area.a);way["highway"]["motorcar"="no"](area.a);way["highway"]["smoothness"="impassable"](area.a);
);out center geom tags;'''
elems=overpass(q).get('elements',[])
ford=[];rivers=[];bridges=[];restr=[]
for e in elems:
    t=e.get('tags') or {};g=geom(e)
    if norm(t.get('ford')) in {'yes','true','1'} or norm(t.get('highway'))=='ford':
      if 'lat'in e:ford.append((float(e['lat']),float(e['lon'])))
      ford.extend(g)
    if norm(t.get('waterway'))=='river':
      rivers.extend((a,b) for a,b in zip(g,g[1:]))
    if t.get('bridge') and norm(t.get('bridge')) not in {'no','false','0'}:
      bridges.extend((a,b) for a,b in zip(g,g[1:]))
    rr=restriction_reason(t)
    if rr:restr.extend((a,b,rr) for a,b in zip(g,g[1:]))
print('ford',len(ford),'river segs',len(rivers),'bridge segs',len(bridges),'restricted segs',len(restr))
ri=defaultdict(list);bi=defaultdict(list);xi=defaultdict(list)
for s in rivers:
  for c in cells(s[0],s[1]):ri[c].append(s)
for s in bridges:
  for c in cells(s[0],s[1]):bi[c].append(s)
for s in restr:
  for c in cells(s[0],s[1]):xi[c].append(s)
def bridge_near(p):
    ia,io=math.floor(p[0]/CELL),math.floor(p[1]/CELL);cand=[]
    for da in (-1,0,1):
      for do in (-1,0,1):cand.extend(bi.get((ia+da,io+do),[]))
    return min((pseg(p,s[0],s[1]) for s in cand),default=999)<.16

def audit(route):
    reasons=[]
    for a0,b0 in zip(route,route[1:]):
      a,b=tuple(a0),tuple(b0)
      # Known ford points.
      if any(pseg(f,a,b)<.025 for f in ford):reasons.append('маршрут проходит через отмеченный брод');break
      # Unbridged river crossing.
      cand=[]
      for c in cells(a,b):cand.extend(ri.get(c,[]))
      for r in cand:
        p=intersect(a,b,r[0],r[1])
        if p and not bridge_near(p):reasons.append('пересечение реки без подтверждённого моста');break
      if reasons:break
      # Explicit road restriction near route segment.
      cand=[]
      for c in cells(a,b):cand.extend(xi.get(c,[]))
      mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
      for x in cand:
        if min(pseg(a,x[0],x[1]),pseg(b,x[0],x[1]),pseg(mid,x[0],x[1]))<.025:
          reasons.append('ограничение дороги: '+x[2]);break
      if reasons:break
    return reasons

official=data.get('settlements',[]);points=official+data.get('extraPlaces',[]);verified=0
for s in points:
    route=s.get('route') or [];s['via']=route_via(route,official,s.get('id')) if len(route)>1 else []
    s['routeSnapKm']=round(hav(tuple(route[-1]),(float(s['lat']),float(s['lon']))),2) if route else None
    reasons=audit(route) if len(route)>1 else ['дорожный маршрут не построен']
    s['routeVerified']=not reasons;s['routeWarnings']=reasons
    if s['routeVerified']:verified+=1
# Propagate to centers/DPK.
byid={s.get('id'):s for s in points}
for group in ('centers','dpk'):
  for s in data.get(group,[]):
    x=byid.get(s.get('id'))
    if x:
      for k in ('route','distanceKm','via','routeSnapKm','routeVerified','routeWarnings'):s[k]=x.get(k)
meta=data.setdefault('meta',{});meta.update({'routingProfile':'firetruck-audited-existing-v2.2','truckProfile':TRUCK,'routeValidation':True,'safeRoutes':verified,'verifiedOfficialRoutes':sum(1 for s in official if s.get('routeVerified')),'unverifiedOfficialRoutes':[s['name'] for s in official if not s.get('routeVerified')],'knownFordCoordinates':len(ford),'riverCrossingAudit':True,'routeAuditMode':'existing OSM road geometry + ford/river/bridge/physical restriction audit'})
DATA.write_text(PREFIX+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print('verified official',meta['verifiedOfficialRoutes'],'/',len(official));print('unverified',meta['unverifiedOfficialRoutes']);print('verified all',verified,'/',len(points))
