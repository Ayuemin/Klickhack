#!/usr/bin/env python3
import json, math, re, time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'app'/'src'/'main'/'assets'/'www'/'data.js'
PREFIX='window.OFFLINE_DATA='
S=requests.Session(); S.headers.update({'User-Agent':'PSCH46-water-sources/2.1'})
OVERPASS=['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']


def norm(s): return re.sub(r'\s+',' ',str(s or '').replace('ё','е').replace('Ё','Е').strip().lower())
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

def rdp(points,eps=.00012):
    if len(points)<=2:return points
    x1,y1=points[0]; x2,y2=points[-1]; den=math.hypot(x2-x1,y2-y1)
    best=-1; bi=0
    for i,(x,y) in enumerate(points[1:-1],1):
        d=math.hypot(x-x1,y-y1) if den==0 else abs((y2-y1)*x-(x2-x1)*y+x2*y1-y2*x1)/den
        if d>best:best=d;bi=i
    if best>eps:
        a=rdp(points[:bi+1],eps);b=rdp(points[bi:],eps);return a[:-1]+b
    return [points[0],points[-1]]

def point_seg_km(p,a,b):
    lat0=math.radians(p[0]); kx=111.320*math.cos(lat0); ky=110.574
    px,py=p[1]*kx,p[0]*ky; ax,ay=a[1]*kx,a[0]*ky; bx,by=b[1]*kx,b[0]*ky
    dx,dy=bx-ax,by-ay
    if dx==0 and dy==0:return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx),py-(ay+t*dy))

def geom_dist_km(p,pts):
    if not pts:return 999
    if len(pts)==1:return hav(p,pts[0])
    return min(point_seg_km(p,a,b) for a,b in zip(pts,pts[1:]))

def feature_type(tags):
    ww=norm(tags.get('waterway')); water=norm(tags.get('water')); lu=norm(tags.get('landuse'))
    if ww=='river':return 'река'
    if ww=='stream':return 'ручей'
    if water=='pond':return 'пруд'
    if water=='lake':return 'озеро'
    if water=='reservoir' or lu=='reservoir':return 'водохранилище'
    if water in {'basin','lagoon'}:return 'водоём'
    return 'водоём'

def stable_name(tags,typ):
    n=(tags.get('name') or '').strip()
    return n if n else f'{typ} без названия'

raw=DATA.read_text(encoding='utf-8').strip(); body=raw[len(PREFIX):]
if body.endswith(';'):body=body[:-1]
data=json.loads(body)
rel=overpass('[out:json][timeout:90];rel["boundary"="administrative"]["name"="Рамешковский муниципальный округ"];out ids;','district')
rels=[e for e in rel.get('elements',[]) if e.get('type')=='relation']
if not rels:raise RuntimeError('District relation not found')
AREA=int(rels[0]['id'])+3600000000
q=f'''[out:json][timeout:300][maxsize:1073741824];area({AREA})->.a;(
 way["waterway"~"river|stream"](area.a);
 way["natural"="water"](area.a);
 relation["natural"="water"](area.a);
 way["landuse"="reservoir"](area.a);
 relation["landuse"="reservoir"](area.a);
);out center geom tags;'''
raw_water=overpass(q,'natural water sources')
features=[]; seen=set()
for e in raw_water.get('elements',[]):
    tags=e.get('tags') or {}; typ=feature_type(tags)
    geom=[(round(float(p['lat']),6),round(float(p['lon']),6)) for p in (e.get('geometry') or []) if 'lat' in p and 'lon' in p]
    c=e.get('center') or {}
    center=(float(c['lat']),float(c['lon'])) if 'lat' in c and 'lon' in c else (geom[len(geom)//2] if geom else None)
    if not center:continue
    # Ignore tiny decorative/artificial basins when type is otherwise unknown.
    if typ=='водоём' and norm(tags.get('water')) in {'basin'} and not tags.get('name'):continue
    name=stable_name(tags,typ)
    # Named rivers/streams are split across many OSM ways; preserve segments for drawing but use a stable source group id.
    group=(typ,norm(tags.get('name')) or f"{e.get('type')}:{e.get('id')}")
    fid=f"{e.get('type','x')[0]}{e.get('id')}"
    pts=rdp(geom,.00009 if typ in {'река','ручей'} else .00013) if len(geom)>2 else geom
    if not pts:pts=[(round(center[0],6),round(center[1],6))]
    key=(fid,typ)
    if key in seen:continue
    seen.add(key)
    features.append({'id':fid,'group':group[0]+'|'+group[1],'name':name,'type':typ,'lat':round(center[0],6),'lon':round(center[1],6),'p':[[a,b] for a,b in pts]})

# For proximity calculations, group contiguous split river/stream ways by type + name. Unnamed features stay separate.
groups={}
for f in features:
    g=groups.setdefault(f['group'],{'name':f['name'],'type':f['type'],'segments':[],'lat':f['lat'],'lon':f['lon']})
    g['segments'].append([tuple(x) for x in f['p']])

def nearest_water(point,limit=5,max_km=7.0):
    rows=[]
    for gid,g in groups.items():
        d=min((geom_dist_km(point,seg) for seg in g['segments']),default=999)
        if d<=max_km:
            rows.append({'group':gid,'name':g['name'],'type':g['type'],'lat':g['lat'],'lon':g['lon'],'distanceKm':round(d,1)})
    rows.sort(key=lambda x:(x['distanceKm'],x['type'],x['name']))
    return rows[:limit]

for s in list(data.get('settlements',[]))+list(data.get('extraPlaces',[])):
    s['nearWater']=nearest_water((float(s['lat']),float(s['lon'])))

# Compact properties for offline app.
data['waterSources']=features
meta=data.setdefault('meta',{})
meta.update({
    'waterLayer':True,
    'waterFeatureCount':len(features),
    'waterGroupCount':len(groups),
    'waterCoverage':'OSM natural water: river, stream, pond, lake, reservoir',
    'waterNearRadiusKm':7.0,
    'waterNearLimit':5
})
DATA.write_text(PREFIX+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print('Water features:',len(features),'groups:',len(groups))
print('Settlements with nearby water:',sum(1 for s in data.get('settlements',[]) if s.get('nearWater')),'/',len(data.get('settlements',[])))
print('data.js bytes:',DATA.stat().st_size)
