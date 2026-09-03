#!/usr/bin/env python3
import json, math, re, time
from collections import defaultdict
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'app'/'src'/'main'/'assets'/'www'/'data.js'
PREFIX='window.OFFLINE_DATA='
AREA=3600570645
CELL=.05
S=requests.Session();S.headers.update({'User-Agent':'PSCH46-water-fast/2.2'})
OVERPASS=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter']

def norm(s):return re.sub(r'\s+',' ',str(s or '').replace('ё','е').replace('Ё','Е').strip().lower())
def hav(a,b):
    la1,lo1=map(math.radians,a);la2,lo2=map(math.radians,b);dla=la2-la1;dlo=lo2-lo1
    h=math.sin(dla/2)**2+math.cos(la1)*math.cos(la2)*math.sin(dlo/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(h)))
def closest(p,a,b):
    lat0=math.radians(p[0]);kx=111.320*math.cos(lat0);ky=110.574
    px,py=p[1]*kx,p[0]*ky;ax,ay=a[1]*kx,a[0]*ky;bx,by=b[1]*kx,b[0]*ky;dx,dy=bx-ax,by-ay
    if dx==0 and dy==0:return hav(p,a),a
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)));q=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))
    return math.hypot(px-(ax+t*dx),py-(ay+t*dy)),q
def overpass(q):
    last=None
    for ep in OVERPASS:
      try:
        print('Water query',ep);r=S.post(ep,data={'data':q},timeout=100);r.raise_for_status();d=r.json();print('elements',len(d.get('elements',[])));return d
      except Exception as e:last=e;print(' failed',repr(e));time.sleep(2)
    raise RuntimeError(f'water Overpass failed: {last}')
def wtype(t):
    ww=norm(t.get('waterway'));w=norm(t.get('water'));lu=norm(t.get('landuse'))
    if ww=='river':return 'река'
    if ww=='stream':return 'ручей'
    if w=='pond':return 'пруд'
    if w=='lake':return 'озеро'
    if w=='reservoir' or lu=='reservoir':return 'водохранилище'
    return 'водоём'
def simplify(points,step=3):
    if len(points)<=40:return points
    out=points[::step]
    if out[-1]!=points[-1]:out.append(points[-1])
    return out

def seg_cells(a,b):
    ia0,ia1=math.floor(min(a[0],b[0])/CELL),math.floor(max(a[0],b[0])/CELL)
    io0,io1=math.floor(min(a[1],b[1])/CELL),math.floor(max(a[1],b[1])/CELL)
    for ia in range(ia0,ia1+1):
      for io in range(io0,io1+1):yield ia,io

raw=DATA.read_text(encoding='utf-8').strip();body=raw[len(PREFIX):];body=body[:-1] if body.endswith(';') else body;data=json.loads(body)
q=f'''[out:json][timeout:100][maxsize:536870912];area({AREA})->.a;(
 way["waterway"~"river|stream"](area.a);
 way["natural"="water"](area.a);relation["natural"="water"](area.a);
 way["landuse"="reservoir"](area.a);relation["landuse"="reservoir"](area.a);
);out center geom tags;'''
elems=overpass(q).get('elements',[])
features=[];groups={};index=defaultdict(set)
for e in elems:
    t=e.get('tags') or {};typ=wtype(t);name=(t.get('name') or '').strip() or f'{typ} без названия'
    g=[(round(float(p['lat']),6),round(float(p['lon']),6)) for p in (e.get('geometry') or []) if 'lat'in p and 'lon'in p]
    c=e.get('center') or {};center=(float(c['lat']),float(c['lon'])) if 'lat'in c and 'lon'in c else (g[len(g)//2] if g else None)
    if not center:continue
    if typ=='водоём' and norm(t.get('water'))=='basin' and not t.get('name'):continue
    gid=typ+'|'+(norm(t.get('name')) or f"{e.get('type')}:{e.get('id')}")
    pts=simplify(g,3 if typ in {'река','ручей'} else 2) if g else [(round(center[0],6),round(center[1],6))]
    f={'id':f"{str(e.get('type','x'))[0]}{e.get('id')}",'group':gid,'name':name,'type':typ,'lat':round(center[0],6),'lon':round(center[1],6),'p':[[a,b] for a,b in pts]}
    features.append(f)
    gr=groups.setdefault(gid,{'name':name,'type':typ,'segments':[]})
    if len(pts)==1:gr['segments'].append((pts[0],pts[0]));index[(math.floor(pts[0][0]/CELL),math.floor(pts[0][1]/CELL))].add(gid)
    else:
      for a,b in zip(pts,pts[1:]):
        gr['segments'].append((a,b))
        for cell in seg_cells(a,b):index[cell].add(gid)

def nearest_water(p,limit=5,maxkm=7.0):
    ia,io=math.floor(p[0]/CELL),math.floor(p[1]/CELL);cand=set()
    # 4 cells covers more than 7 km even in longitude at this latitude.
    for da in range(-4,5):
      for do in range(-4,5):cand.update(index.get((ia+da,io+do),()))
    rows=[]
    for gid in cand:
      gr=groups[gid];best=(999,None)
      for a,b in gr['segments']:
        d,q=closest(p,a,b)
        if d<best[0]:best=(d,q)
      if best[0]<=maxkm and best[1]:rows.append({'group':gid,'name':gr['name'],'type':gr['type'],'lat':round(best[1][0],6),'lon':round(best[1][1],6),'distanceKm':round(best[0],1)})
    rows.sort(key=lambda x:(x['distanceKm'],x['type'],x['name']));return rows[:limit]

points=list(data.get('settlements',[]))+list(data.get('extraPlaces',[]))
for i,s in enumerate(points,1):
    s['nearWater']=nearest_water((float(s['lat']),float(s['lon'])))
    if i%75==0:print('water nearest',i,'/',len(points))
data['waterSources']=features
meta=data.setdefault('meta',{});meta.update({'waterLayer':True,'waterFeatureCount':len(features),'waterGroupCount':len(groups),'waterCoverage':'OSM natural water: river, stream, pond, lake, reservoir','waterNearRadiusKm':7.0,'waterNearLimit':5,'waterSpatialIndex':True})
DATA.write_text(PREFIX+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print('Water features',len(features),'groups',len(groups),'settlements with water',sum(1 for s in data.get('settlements',[]) if s.get('nearWater')))
