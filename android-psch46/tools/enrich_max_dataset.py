#!/usr/bin/env python3
import json, math, re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "src" / "main" / "assets" / "www" / "data.js"
SOURCE = ROOT / "all_named_source.json"

PREFIX = "window.OFFLINE_DATA="


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("ё", "е").replace("Ё", "Е").strip().lower())


def hav(a, b):
    lat1, lon1 = map(math.radians, a); lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1; dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(h)))


def load_data():
    raw = DATA.read_text(encoding="utf-8").strip()
    if not raw.startswith(PREFIX):
        raise RuntimeError("Unexpected data.js format")
    body = raw[len(PREFIX):]
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def former_from_legacy_territory(value):
    v = (value or "").strip()
    if norm(v) == "рамешки":
        return "Рамешки"
    return re.sub(r"\s+—\s+бывшее сельское поселение\s*$", "", v).strip()


# Current territorial names from the official Rameshki municipal administration site.
# Historical settlement names are retained because the canonical list is grouped by the former settlements.
TERRITORIES = [
    {"key":"rameshki","name":"Рамешки","former":"Рамешки","center":"Рамешки"},
    {"key":"aleshino","name":"Алешинская сельская территория","former":"Алёшино","center":"Алёшино"},
    {"key":"zamyt","name":"Замытская сельская территория","former":"Высоково","center":"Замытье"},
    {"key":"kushalino","name":"Кушалинская сельская территория","former":"Кушалино","center":"Кушалино"},
    {"key":"nekrasovo","name":"Некрасовская сельская территория","former":"Некрасово","center":"Некрасово"},
    {"key":"zastolbye","name":"Застолбская сельская территория","former":"Застолбье","center":"Застолбье"},
    {"key":"kiverichi","name":"Киверичская сельская территория","former":"Киверичи","center":"Киверичи"},
    {"key":"nikolskoye","name":"Никольская сельская территория","former":"Никольское","center":"Никольское"},
    {"key":"zaklinye","name":"Заклинская сельская территория","former":"Заклинье","center":"Заклинье"},
    {"key":"vednoe","name":"Ведновская сельская территория","former":"Ведное","center":"Ведное"},
    {"key":"ilgoschi","name":"Ильгощинская сельская территория","former":"Ильгощи","center":"Ильгощи"},
]
BY_FORMER = {norm(x["former"]): x for x in TERRITORIES}


data = load_data()
official = list(data.get("settlements", []))
if len(official) != 306:
    raise RuntimeError(f"Expected 306 verified official settlements, got {len(official)}")

# Upgrade type labels and attach the current rural territory metadata.
for s in official:
    t = norm(s.get("type"))
    if t == "населенный пункт":
        # Keep old generic values only where source type is genuinely unknown.
        pass
    former = former_from_legacy_territory(s.get("territory"))
    td = BY_FORMER.get(norm(former))
    if td:
        s["territoryKey"] = td["key"]
        s["territory"] = td["name"]
        s["formerSettlement"] = td["former"]
    else:
        s["territoryKey"] = "unknown"
        s["formerSettlement"] = former
    s["isOfficial"] = True

# Fix a few type labels that older parsing reduced to a generic point.
# The canonical district list contains 287 villages, 17 sela, 1 pgt and 1 settlement.
for s in official:
    if norm(s["name"]) == "рамешки":
        s["type"] = "пгт"
    elif norm(s["name"]) == "городковский":
        s["type"] = "посёлок"

# Territory counts and centers.
by_name = defaultdict(list)
for s in official:
    by_name[norm(s["name"])].append(s)

territory_rows = []
centers = []
for td in TERRITORIES:
    members = [s for s in official if s.get("territoryKey") == td["key"]]
    center_candidates = by_name.get(norm(td["center"]), [])
    center = None
    if center_candidates:
        same = [s for s in center_candidates if s.get("territoryKey") == td["key"]]
        center = (same or center_candidates)[0]
    row = dict(td)
    row["count"] = len(members)
    if center:
        row["centerId"] = center["id"]
        centers.append({
            "id": center["id"], "name": center["name"], "type": center.get("type"),
            "territoryKey": td["key"], "territory": td["name"],
            "formerSettlement": td["former"], "lat": center["lat"], "lon": center["lon"],
            "route": center.get("route", []), "distanceKm": center.get("distanceKm"),
            "isOfficial": True, "isCenter": True
        })
    territory_rows.append(row)

# Preserve every named place/locality object captured before the canonical 306-item filter.
source = json.loads(SOURCE.read_text(encoding="utf-8")) if SOURCE.exists() else []
print("Full captured named layer:", len(source))

# Remove duplicate OSM representations of official points, then de-duplicate remaining named objects.
extra = []
for p in source:
    name = (p.get("name") or "").strip()
    if not name or not p.get("lat") or not p.get("lon"):
        continue
    pt = (float(p["lat"]), float(p["lon"]))
    same_off = [s for s in by_name.get(norm(name), []) if hav(pt, (s["lat"], s["lon"])) < 1.2]
    if same_off:
        continue
    # Suppress duplicate node/way/relation representations of the same extra place.
    dup = None
    for e in extra:
        if norm(e["name"]) == norm(name) and hav(pt, (e["lat"], e["lon"])) < 0.7:
            dup = e
            break
    if dup:
        # Prefer a version that has a route.
        if not dup.get("route") and p.get("route"):
            dup["route"] = p.get("route", [])
            dup["distanceKm"] = p.get("distanceKm")
        continue
    nearest = min(official, key=lambda s: hav(pt, (s["lat"], s["lon"])))
    typ = p.get("type") or "именованное место"
    if norm(typ) == "населенный пункт":
        typ = "местность / урочище"
    extra.append({
        "id": "extra-" + str(len(extra) + 1),
        "name": name,
        "type": typ,
        "territoryKey": nearest.get("territoryKey", "unknown"),
        "territory": nearest.get("territory", "Рамешковский муниципальный округ"),
        "formerSettlement": nearest.get("formerSettlement", ""),
        "lat": round(pt[0], 6), "lon": round(pt[1], 6),
        "route": p.get("route", []), "distanceKm": p.get("distanceKm"),
        "isOfficial": False, "isExtra": True
    })

# Enrich DPK objects with ids/routes so they can be a true training mode.
dpk_names = ["Алёшино", "Киверичи", "Застолбье", "Никольское"]
dpk = []
for name in dpk_names:
    cands = by_name.get(norm(name), [])
    if cands:
        s = cands[0]
        dpk.append({
            "id": s["id"], "name": s["name"], "type": s.get("type"),
            "territoryKey": s.get("territoryKey"), "territory": s.get("territory"),
            "formerSettlement": s.get("formerSettlement"),
            "lat": s["lat"], "lon": s["lon"], "route": s.get("route", []),
            "distanceKm": s.get("distanceKm"), "isOfficial": True, "isDpk": True
        })

# Counts are deliberately included in the dataset so the UI can expose them transparently.
type_counts = defaultdict(int)
for s in official:
    type_counts[s.get("type") or "населённый пункт"] += 1

data["settlements"] = official
data["extraPlaces"] = extra
data["territories"] = territory_rows
data["centers"] = centers
data["dpk"] = dpk
meta = data.setdefault("meta", {})
meta.update({
    "version": "2.0-max",
    "officialCount": len(official),
    "extraNamedCount": len(extra),
    "totalTrainingPoints": len(official) + len(extra),
    "centerCount": len(centers),
    "dpkCount": len(dpk),
    "territoryCount": len(territory_rows),
    "typeCounts": dict(type_counts),
    "territoryModel": "current-administration-plus-former-settlement",
    "maxDataset": True
})

out = PREFIX + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
DATA.write_text(out, encoding="utf-8")
print("Official settlements:", len(official))
print("Extra named places:", len(extra))
print("Centers:", len(centers), "DPK:", len(dpk), "Territories:", len(territory_rows))
print("Type counts:", dict(type_counts))
print("Final data.js bytes:", len(out.encode("utf-8")))
