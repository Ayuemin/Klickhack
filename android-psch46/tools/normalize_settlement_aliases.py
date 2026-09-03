#!/usr/bin/env python3
import json, re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'app' / 'src' / 'main' / 'assets' / 'www' / 'data.js'
raw = DATA.read_text(encoding='utf-8').strip()
prefix = 'window.OFFLINE_DATA='
body = raw[len(prefix):]
if body.endswith(';'):
    body = body[:-1]
data = json.loads(body)

def norm(s):
    return re.sub(r'\s+', ' ', (s or '').replace('ё','е').replace('Ё','Е').strip().lower())

aliases = {
    'филиппково': 'Филипково',
}
changed = 0
for s in data.get('settlements', []):
    k = norm(s.get('name'))
    if k in aliases:
        s['name'] = aliases[k]
        changed += 1

DATA.write_text(prefix + json.dumps(data, ensure_ascii=False, separators=(',',':')) + ';\n', encoding='utf-8')
print('Normalized settlement aliases:', changed)
