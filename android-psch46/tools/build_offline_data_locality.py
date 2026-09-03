#!/usr/bin/env python3
from pathlib import Path
src = Path(__file__).with_name('build_offline_data.py')
code = src.read_text(encoding='utf-8')
code = code.replace('town|village|hamlet|isolated_dwelling', 'town|village|hamlet|isolated_dwelling|locality')
old = '''OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]'''
new = '''OVERPASS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]'''
code = code.replace(old, new)
exec(compile(code, str(src), 'exec'))
