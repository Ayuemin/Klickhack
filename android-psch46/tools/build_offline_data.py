#!/usr/bin/env python3
import json, math, heapq, re, time
from collections import defaultdict
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "app" / "src" / "main" / "assets" / "www"
WWW.mkdir(parents=True, exist_ok=True)

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]
UA = "PSCH46-Rameshki-Offline-Trainer/1.0 (educational offline map build)"
S = requests.Session(); S.headers.update({"User-Agent": UA})


def overpass(query, label):
    last = None
    for endpoint in OVERPASS:
        for attempt in range(3):
            try:
                print(f"Overpass {label}: {endpoint}, attempt {attempt+1}")
                r = S.post(endpoint, data={"data": query}, timeout=300)
                r.raise_for_status()
                data = r.json()
                print(f"  {len(data.get('elements', []))} elements")
                return data
            except Exception as e:
                last = e
                print("  failed:", repr(e))
                time.sleep(3 + attempt * 4)
    raise RuntimeError(f"Overpass failed for {label}: {last}")


def center(el):
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    c = el.get("center") or {}
    if "lat" in c and "lon" in c:
        return float(c["lat"]), float(c["lon"])
    return None


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("ё", "е").replace("Ё", "Е").strip().lower())


def hav(a, b):
    lat1, lon1 = map(math.radians, a); lat2, lon2 = map(math.radians, b)
    dlat = lat2-lat1; dlon = lon2-lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(h)))


def rdp(points, eps=0.00035):
    if len(points) <= 2: return points
    x1,y1 = points[0]; x2,y2 = points[-1]
    den = math.hypot(x2-x1, y2-y1)
    best_i, best = 0, -1
    for i,(x,y) in enumerate(points[1:-1],1):
        if den == 0: d = math.hypot(x-x1, y-y1)
        else: d = abs((y2-y1)*x - (x2-x1)*y + x2*y1-y2*x1)/den
        if d > best: best, best_i = d, i
    if best > eps:
        a = rdp(points[:best_i+1], eps); b = rdp(points[best_i:], eps)
        return a[:-1] + b
    return [points[0], points[-1]]


def wiki_records():
    url = "https://ru.wikipedia.org/wiki/%D0%A1%D0%BF%D0%B8%D1%81%D0%BE%D0%BA_%D0%BD%D0%B0%D1%81%D0%B5%D0%BB%D1%91%D0%BD%D0%BD%D1%8B%D1%85_%D0%BF%D1%83%D0%BD%D0%BA%D1%82%D0%BE%D0%B2_%D0%A0%D0%B0%D0%BC%D0%B5%D1%88%D0%BA%D0%BE%D0%B2%D1%81%D0%BA%D0%BE%D0%B3%D0%BE_%D1%80%D0%B0%D0%B9%D0%BE%D0%BD%D0%B0"
    try:
        r = S.get(url, timeout=60); r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for table in soup.find_all("table"):
            txt = table.get_text(" ", strip=True)
            if "Название" not in txt or "Поселение" not in txt or "Бывший округ" not in txt:
                continue
            rows = []
            headers = [x.get_text(" ", strip=True) for x in table.find("tr").find_all(["th","td"])]
            try:
                i_type = next(i for i,h in enumerate(headers) if "Тип" in h)
                i_name = next(i for i,h in enumerate(headers) if "Название" in h)
                i_mun = next(i for i,h in enumerate(headers) if "Поселение" in h)
            except StopIteration:
                continue
            for tr in table.find_all("tr")[1:]:
                cells = [x.get_text(" ", strip=True) for x in tr.find_all(["th","td"])]
                if len(cells) <= max(i_type,i_name,i_mun): continue
                name = cells[i_name].strip(); typ = cells[i_type].strip(); mun = cells[i_mun].strip()
                if not name or not mun: continue
                mun = re.sub(r"^(СП|ГП)\s+", "", mun)
                rows.append({"name":name,"type":typ,"mun":mun})
            if len(rows) > 200:
                print("Wikipedia records:", len(rows)); return rows
    except Exception as e:
        print("Wikipedia mapping unavailable:", repr(e))
    return []

print("Finding Rameshki district relation...")
rel_data = overpass('[out:json][timeout:90];rel["boundary"="administrative"]["name"~"Рамешковск"];out ids tags center;', 'district relation')
rels = [e for e in rel_data.get('elements',[]) if e.get('type')=='relation']
if not rels: raise RuntimeError('Rameshki administrative relation not found')

def rel_score(e):
    n = e.get('tags',{}).get('name','')
    score = 0
    if 'муниципальный округ' in n.lower(): score += 20
    if n == 'Рамешковский муниципальный округ': score += 50
    if e.get('tags',{}).get('admin_level') in ('6','7','8'): score += 5
    return score
rel = max(rels, key=rel_score)
RID = int(rel['id']); AREA = RID + 3600000000
print('Using relation', RID, rel.get('tags',{}).get('name'), 'area', AREA)

sett_q = f'''[out:json][timeout:180];area({AREA})->.a;(node["place"~"town|village|hamlet|isolated_dwelling"](area.a);way["place"~"town|village|hamlet|isolated_dwelling"](area.a);relation["place"~"town|village|hamlet|isolated_dwelling"](area.a););out center tags;'''
sett_raw = overpass(sett_q, 'settlements')
sett_osm=[]
for e in sett_raw.get('elements',[]):
    c=center(e); t=e.get('tags',{}); name=t.get('name')
    if not c or not name: continue
    sett_osm.append({'osm_id':f"{e['type'][0]}{e['id']}", 'name':name, 'place':t.get('place','village'), 'lat':c[0], 'lon':c[1]})
print('OSM named settlements:', len(sett_osm))

road_q = f'''[out:json][timeout:300][maxsize:1073741824];area({AREA})->.a;way["highway"~"trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|track"](area.a);out geom tags;'''
road_raw = overpass(road_q, 'roads')
roads=[]
for e in road_raw.get('elements',[]):
    geom=e.get('geometry') or []
    if len(geom)<2: continue
    cls=e.get('tags',{}).get('highway','unclassified')
    pts=[[round(float(p['lat']),6),round(float(p['lon']),6)] for p in geom if 'lat' in p and 'lon' in p]
    if len(pts)>=2: roads.append({'c':cls,'p':pts})
print('Road ways:', len(roads))

fire_q=f'''[out:json][timeout:90];area({AREA})->.a;(node["amenity"="fire_station"](area.a);way["amenity"="fire_station"](area.a);relation["amenity"="fire_station"](area.a););out center tags;'''
fire_raw=overpass(fire_q,'fire stations')

rameshki_candidates=[s for s in sett_osm if norm(s['name'])=='рамешки']
rameshki=(rameshki_candidates[0]['lat'],rameshki_candidates[0]['lon']) if rameshki_candidates else (57.343,36.046)
fires=[]
for e in fire_raw.get('elements',[]):
    c=center(e)
    if c: fires.append((hav(c,rameshki),c,e.get('tags',{})))
if fires:
    fires.sort(key=lambda x:(0 if '46' in x[2].get('name','') else 1,x[0]))
    station_pt=fires[0][1]
else:
    station_pt=rameshki
station={'name':'ПСЧ-46 · Рамешки, ул. Дюканова, 6','lat':round(station_pt[0],6),'lon':round(station_pt[1],6)}
print('Station:', station)

# Former rural-settlement mapping from the historical district list.
wiki=wiki_records(); wiki_by=defaultdict(list)
for r in wiki: wiki_by[norm(r['name'])].append(r)
osm_by=defaultdict(list)
for s in sett_osm: osm_by[norm(s['name'])].append(s)

mun_names=['Алёшино','Ведное','Высоково','Заклинье','Застолбье','Ильгощи','Киверичи','Кушалино','Некрасово','Никольское','Рамешки']
mun_centers={}
for m in mun_names:
    cs=osm_by.get(norm(m),[])
    if cs: mun_centers[norm(m)]=(cs[0]['lat'],cs[0]['lon'])

def clean_type(t, place):
    x=(t or '').lower()
    if 'пгт' in x or place=='town': return 'посёлок'
    if 'село' in x: return 'село'
    if 'дер' in x: return 'деревня'
    return {'village':'село','hamlet':'деревня','isolated_dwelling':'деревня'}.get(place,'населённый пункт')

def territory(mun):
    m=re.sub(r"^(Сельское поселение|Городское поселение|СП|ГП)\s+",'',mun or '').strip()
    if not m: return 'Рамешковский муниципальный округ'
    if norm(m)=='рамешки': return 'Рамешки'
    return m + ' — бывшее сельское поселение'

settlements=[]; used=set()
if wiki:
    for key,records in wiki_by.items():
        cands=osm_by.get(key,[])[:]
        if not cands: continue
        for rec in records:
            avail=[c for c in cands if c['osm_id'] not in used]
            if not avail: break
            mc=mun_centers.get(norm(rec['mun']))
            pick=min(avail,key=lambda c:hav((c['lat'],c['lon']),mc)) if mc else avail[0]
            used.add(pick['osm_id'])
            settlements.append({
                'id':pick['osm_id'],'name':pick['name'],'type':clean_type(rec['type'],pick['place']),
                'territory':territory(rec['mun']),'lat':round(pick['lat'],6),'lon':round(pick['lon'],6)
            })
for s in sett_osm:
    if s['osm_id'] in used: continue
    settlements.append({'id':s['osm_id'],'name':s['name'],'type':clean_type('',s['place']),'territory':'Рамешковский муниципальный округ','lat':round(s['lat'],6),'lon':round(s['lon'],6)})
# Stable ordering and remove exact duplicate OSM objects.
uniq={s['id']:s for s in settlements}; settlements=sorted(uniq.values(),key=lambda s:(norm(s['name']),s['id']))
print('Final settlements:',len(settlements))

# Graph for one-source shortest paths.
factors={'trunk':1.0,'primary':1.0,'secondary':1.03,'tertiary':1.07,'unclassified':1.12,'residential':1.18,'living_street':1.22,'service':1.30,'track':1.65}
g=defaultdict(list); coords={}
def key(p): return (round(p[0],6),round(p[1],6))
for w in roads:
    pts=w['p']; f=factors.get(w['c'],1.2)
    for a,b in zip(pts,pts[1:]):
        ka,kb=key(a),key(b); coords[ka]=ka; coords[kb]=kb
        d=hav(ka,kb); wt=d*f
        g[ka].append((kb,wt,d)); g[kb].append((ka,wt,d))
print('Road graph nodes:',len(g))
if not g: raise RuntimeError('Empty road graph')
all_nodes=list(g.keys())
def nearest(pt):
    # District scale: simple scan is reliable and fast enough for ~300 targets.
    return min(all_nodes,key=lambda n:(n[0]-pt[0])**2 + ((n[1]-pt[1])*math.cos(math.radians(pt[0])))**2)
start=nearest((station['lat'],station['lon']))
dist={start:0.0}; realdist={start:0.0}; prev={}; pq=[(0.0,start)]
while pq:
    d,u=heapq.heappop(pq)
    if d!=dist.get(u): continue
    for v,w,rd in g[u]:
        nd=d+w
        if nd < dist.get(v,float('inf')):
            dist[v]=nd; realdist[v]=realdist[u]+rd; prev[v]=u; heapq.heappush(pq,(nd,v))

def route_to(pt):
    t=nearest(pt)
    if t not in dist: return [],None
    path=[t]; cur=t; guard=0
    while cur!=start and cur in prev and guard<200000:
        cur=prev[cur]; path.append(cur); guard+=1
    if path[-1]!=start: return [],None
    path.reverse(); path=[[p[0],p[1]] for p in path]
    path=rdp(path,0.00028)
    return [[round(a,6),round(b,6)] for a,b in path], round(realdist[t],1)

for i,s in enumerate(settlements):
    r,d=route_to((s['lat'],s['lon'])); s['route']=r; s['distanceKm']=d
    if (i+1)%50==0: print('Routes',i+1,'/',len(settlements))

# Map bbox from settlements, padded slightly.
lats=[s['lat'] for s in settlements]; lons=[s['lon'] for s in settlements]
mnla,mxla=min(lats),max(lats); mnlo,mxlo=min(lons),max(lons)
padla=(mxla-mnla)*0.035; padlo=(mxlo-mnlo)*0.035
bbox=[[round(mnla-padla,6),round(mnlo-padlo,6)],[round(mxla+padla,6),round(mxlo+padlo,6)]]

dpk=[]
for name in ['Алёшино','Киверичи','Застолбье','Никольское']:
    cands=[s for s in settlements if norm(s['name'])==norm(name)]
    if cands: dpk.append({'name':name,'lat':cands[0]['lat'],'lon':cands[0]['lon']})

# Keep the road network visually useful while limiting JSON size.
road_out=[]
for w in roads:
    pts=rdp(w['p'],0.00018) if len(w['p'])>3 else w['p']
    road_out.append({'c':w['c'],'p':pts})

data={
 'meta':{'title':'Район выезда ПСЧ-46','district':'Рамешковский муниципальный округ','offline':True,'osmAttribution':'© OpenStreetMap contributors'},
 'bbox':bbox,'station':station,'dpk':dpk,'roads':road_out,'settlements':settlements
}
out='window.OFFLINE_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n'
(WWW/'data.js').write_text(out,encoding='utf-8')
print('Wrote',WWW/'data.js','bytes',len(out.encode('utf-8')))
print('Routes available:',sum(1 for s in settlements if s['route']),'/',len(settlements))
