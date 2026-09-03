#!/usr/bin/env python3
import json, math, re, time
from collections import defaultdict
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "src" / "main" / "assets" / "www" / "data.js"
UA = "PSCH46-Rameshki-Offline-Trainer/1.1 (catalog verification build)"
S = requests.Session(); S.headers.update({"User-Agent": UA})
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("ё", "е").replace("Ё", "Е").strip().lower())


def hav(a, b):
    lat1, lon1 = map(math.radians, a); lat2, lon2 = map(math.radians, b)
    dlat = lat2-lat1; dlon = lon2-lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(h)))


def load_data():
    raw = DATA.read_text(encoding="utf-8").strip()
    prefix = "window.OFFLINE_DATA="
    if not raw.startswith(prefix):
        raise RuntimeError("Unexpected data.js format")
    body = raw[len(prefix):]
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def official_records():
    url = "https://ru.wikipedia.org/wiki/%D0%A1%D0%BF%D0%B8%D1%81%D0%BE%D0%BA_%D0%BD%D0%B0%D1%81%D0%B5%D0%BB%D1%91%D0%BD%D0%BD%D1%8B%D1%85_%D0%BF%D1%83%D0%BD%D0%BA%D1%82%D0%BE%D0%B2_%D0%A0%D0%B0%D0%BC%D0%B5%D1%88%D0%BA%D0%BE%D0%B2%D1%81%D0%BA%D0%BE%D0%B3%D0%BE_%D1%80%D0%B0%D0%B9%D0%BE%D0%BD%D0%B0"
    r = S.get(url, timeout=90); r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    for table in soup.find_all("table"):
        txt = table.get_text(" ", strip=True)
        if "Название" not in txt or "Поселение" not in txt or "Бывший округ" not in txt:
            continue
        headers = [x.get_text(" ", strip=True) for x in table.find("tr").find_all(["th","td"])]
        try:
            i_type = next(i for i,h in enumerate(headers) if "Тип" in h)
            i_name = next(i for i,h in enumerate(headers) if "Название" in h)
            i_mun = next(i for i,h in enumerate(headers) if "Поселение" in h)
        except StopIteration:
            continue
        rows=[]
        for tr in table.find_all("tr")[1:]:
            cells=[x.get_text(" ", strip=True) for x in tr.find_all(["th","td"])]
            if len(cells) <= max(i_type,i_name,i_mun):
                continue
            name=cells[i_name].strip(); typ=cells[i_type].strip(); mun=cells[i_mun].strip()
            if not name or not mun:
                continue
            mun=re.sub(r"^(СП|ГП)\s+", "", mun).strip()
            rows.append({"name":name,"type":typ,"mun":mun})
        if len(rows) >= 300:
            print("Canonical active settlements:", len(rows))
            return rows
    raise RuntimeError("Canonical settlement table not found")


def clean_type(t):
    x=(t or "").lower()
    if "пгт" in x: return "посёлок"
    if "село" in x: return "село"
    if "дер" in x: return "деревня"
    return "населённый пункт"


def territory(mun):
    m=(mun or "").strip()
    if norm(m)=="рамешки": return "Рамешки"
    return m + " — бывшее сельское поселение"


def center(el):
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"])
    c=el.get("center") or {}
    if "lat" in c and "lon" in c:
        return float(c["lat"]), float(c["lon"])
    return None


def overpass(q, label):
    last=None
    for ep in OVERPASS:
        for attempt in range(3):
            try:
                print("Overpass", label, ep, "attempt", attempt+1)
                r=S.post(ep,data={"data":q},timeout=240); r.raise_for_status()
                return r.json()
            except Exception as e:
                last=e; print(" failed",repr(e)); time.sleep(3+attempt*3)
    raise RuntimeError(f"Overpass failed {label}: {last}")


def broad_candidates(names, bbox):
    if not names: return []
    south,west=bbox[0]; north,east=bbox[1]
    out=[]
    unique=sorted(set(names), key=norm)
    for start in range(0,len(unique),24):
        batch=unique[start:start+24]
        pattern="^("+"|".join(re.escape(x).replace('\\ ', ' ') for x in batch)+")$"
        pattern=pattern.replace('"','\\"')
        q=f'''[out:json][timeout:180];(node["name"~"{pattern}"]({south},{west},{north},{east});way["name"~"{pattern}"]({south},{west},{north},{east});relation["name"~"{pattern}"]({south},{west},{north},{east}););out center tags;'''
        d=overpass(q,f"fallback names {start+1}-{start+len(batch)}")
        for e in d.get("elements",[]):
            c=center(e); tags=e.get("tags",{}); name=tags.get("name")
            if not c or not name: continue
            out.append({
                "id":f"fallback-{e.get('type','x')[0]}{e.get('id')}",
                "name":name,"lat":round(c[0],6),"lon":round(c[1],6),
                "place":tags.get("place",""),"tags":tags
            })
    print("Broad fallback candidates:",len(out))
    return out


def nominatim(name, mun, bbox):
    south,west=bbox[0]; north,east=bbox[1]
    q=f"{name}, {mun}, Рамешковский муниципальный округ, Тверская область, Россия"
    try:
        r=S.get("https://nominatim.openstreetmap.org/search",params={"q":q,"format":"jsonv2","limit":5,"countrycodes":"ru"},timeout=60)
        r.raise_for_status(); rows=r.json()
        time.sleep(1.05)
        for x in rows:
            lat=float(x["lat"]); lon=float(x["lon"])
            if south <= lat <= north and west <= lon <= east:
                return {"id":"nominatim-"+str(x.get("osm_id",name)),"name":name,"lat":round(lat,6),"lon":round(lon,6),"place":""}
    except Exception as e:
        print("Nominatim failed",name,repr(e))
    return None


def nearest_route_source(pt, settlements, used_ids=None):
    best=None
    for s in settlements:
        if not s.get("route"): continue
        d=hav(pt,(s["lat"],s["lon"]))
        if best is None or d<best[0]: best=(d,s)
    return best


def route_for_new(pt, source_settlements):
    best=nearest_route_source(pt, source_settlements)
    if not best: return [],None
    d,s=best
    if d>4.0:
        return [],None
    route=[list(p) for p in s.get("route",[])]
    if not route: return [],None
    if hav(tuple(route[-1]),pt)>0.03:
        route.append([round(pt[0],6),round(pt[1],6)])
    dist=(s.get("distanceKm") or 0)+d
    return route,round(dist,1)


data=load_data()
records=official_records()
source=list(data.get("settlements",[]))
by_name=defaultdict(list)
for s in source:
    by_name[norm(s.get("name"))].append(s)

# Territory anchor points help distinguish same-name villages in different former settlements.
mun_centers={}
for rec in records:
    k=norm(rec["mun"])
    if k in mun_centers: continue
    cands=by_name.get(k,[])
    if cands: mun_centers[k]=(cands[0]["lat"],cands[0]["lon"])

used=set(); final=[]; unresolved=[]
for idx,rec in enumerate(records,1):
    cands=[s for s in by_name.get(norm(rec["name"]),[]) if s.get("id") not in used]
    pick=None
    if cands:
        mc=mun_centers.get(norm(rec["mun"]))
        if mc:
            pick=min(cands,key=lambda s:hav((s["lat"],s["lon"]),mc))
        else:
            pick=cands[0]
    if pick:
        used.add(pick.get("id"))
        final.append({
            "id":f"official-{idx}","name":rec["name"],"type":clean_type(rec["type"]),
            "territory":territory(rec["mun"]),"lat":pick["lat"],"lon":pick["lon"],
            "route":pick.get("route",[]),"distanceKm":pick.get("distanceKm")
        })
    else:
        unresolved.append((idx,rec))

print("Matched from place/locality layer:",len(final),"unresolved:",len(unresolved))

fallback=broad_candidates([r["name"] for _,r in unresolved],data["bbox"])
fb_by=defaultdict(list)
for x in fallback: fb_by[norm(x["name"])].append(x)
remaining=[]
for idx,rec in unresolved:
    cands=fb_by.get(norm(rec["name"]),[])
    mc=mun_centers.get(norm(rec["mun"]))
    # Prefer real place features, then administrative boundaries, then nearest named feature.
    def score(x):
        tags=x.get("tags",{})
        pri=0
        if x.get("place") in ("town","village","hamlet","locality","isolated_dwelling"): pri-=100
        if tags.get("boundary")=="administrative": pri-=30
        if tags.get("highway") or tags.get("amenity") or tags.get("shop"): pri+=25
        dd=hav((x["lat"],x["lon"]),mc) if mc else 0
        return pri+dd
    pick=min(cands,key=score) if cands else None
    if pick:
        route,km=route_for_new((pick["lat"],pick["lon"]),source)
        final.append({"id":f"official-{idx}","name":rec["name"],"type":clean_type(rec["type"]),"territory":territory(rec["mun"]),"lat":pick["lat"],"lon":pick["lon"],"route":route,"distanceKm":km})
    else:
        remaining.append((idx,rec))

print("After broad fallback unresolved:",len(remaining))
last=[]
for idx,rec in remaining:
    pick=nominatim(rec["name"],rec["mun"],data["bbox"])
    if not pick:
        last.append((idx,rec)); continue
    route,km=route_for_new((pick["lat"],pick["lon"]),source)
    final.append({"id":f"official-{idx}","name":rec["name"],"type":clean_type(rec["type"]),"territory":territory(rec["mun"]),"lat":pick["lat"],"lon":pick["lon"],"route":route,"distanceKm":km})

if last:
    print("UNRESOLVED CANONICAL SETTLEMENTS:")
    for _,r in last: print(" -",r["name"],"/",r["mun"])
    raise RuntimeError(f"Catalog incomplete: {len(last)} canonical settlements unresolved")

# Preserve canonical table order; every row must be present exactly once.
final=sorted(final,key=lambda s:int(s["id"].split("-")[-1]))
if len(final)!=len(records):
    raise RuntimeError(f"Catalog count mismatch: final={len(final)} records={len(records)}")

# DPK markers from canonical settlements.
dpk=[]
for name in ["Алёшино","Киверичи","Застолбье","Никольское"]:
    cands=[s for s in final if norm(s["name"])==norm(name)]
    if cands: dpk.append({"name":name,"lat":cands[0]["lat"],"lon":cands[0]["lon"]})

data["settlements"]=final
data["dpk"]=dpk
data.setdefault("meta",{})["catalog"]="canonical-active-list"
data["meta"]["catalogCount"]=len(final)
data["meta"]["catalogVerified"]=True

out="window.OFFLINE_DATA="+json.dumps(data,ensure_ascii=False,separators=(",",":"))+";\n"
DATA.write_text(out,encoding="utf-8")
print("Verified canonical catalog:",len(final))
print("Routes available:",sum(1 for s in final if s.get("route")),"/",len(final))
