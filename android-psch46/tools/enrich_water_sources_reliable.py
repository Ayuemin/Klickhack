#!/usr/bin/env python3
from pathlib import Path
src=Path(__file__).with_name('enrich_water_sources.py')
code=src.read_text(encoding='utf-8')
code=code.replace(
"OVERPASS=['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']",
"OVERPASS=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter']"
)
code=code.replace('for attempt in range(4):','for attempt in range(1):')
# Special modes (centers / DPK) reference the same official settlements, so copy their nearby-water result too.
code=code.replace(
"data['waterSources']=features",
"byid={s.get('id'):s for s in list(data.get('settlements',[]))+list(data.get('extraPlaces',[]))}\nfor group in ('centers','dpk'):\n    for s in data.get(group,[]):\n        srcp=byid.get(s.get('id'))\n        if srcp is not None:s['nearWater']=srcp.get('nearWater',[])\ndata['waterSources']=features"
)
exec(compile(code,str(src),'exec'))
