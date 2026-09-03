#!/usr/bin/env python3
from pathlib import Path
src=Path(__file__).with_name('audit_route_river_crossings.py')
code=src.read_text(encoding='utf-8')
code=code.replace(
"OVERPASS=['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']",
"OVERPASS=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass.private.coffee/api/interpreter','https://overpass-api.de/api/interpreter']"
)
exec(compile(code,str(src),'exec'))
