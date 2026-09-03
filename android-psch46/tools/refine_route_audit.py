#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'app'/'src'/'main'/'assets'/'www'/'data.js'
PREFIX='window.OFFLINE_DATA='
raw=DATA.read_text(encoding='utf-8').strip();body=raw[len(PREFIX):];body=body[:-1] if body.endswith(';') else body
d=json.loads(body)
points=list(d.get('settlements',[]))+list(d.get('extraPlaces',[]))
counts=Counter()
for s in points:
    warnings=list(s.get('routeWarnings') or [])
    hard=[];soft=[]
    for w in warnings:
        lw=w.lower()
        if 'брод' in lw or 'motor_vehicle=no' in lw or 'motorcar=no' in lw or 'непроезжая' in lw or any(x in lw for x in ('масса:','высота:','ширина:','длина:')):
            hard.append(w);counts['hard']+=1
        else:
            soft.append(w);counts['soft']+=1
    s['routeHardWarnings']=hard
    s['routeCautionWarnings']=soft
    s['routeVerified']=bool(s.get('route')) and not hard
    s['routeCaution']=bool(soft)
byid={x.get('id'):x for x in points}
for group in ('centers','dpk'):
    for s in d.get(group,[]):
        x=byid.get(s.get('id'))
        if x:
            for k in ('routeVerified','routeCaution','routeWarnings','routeHardWarnings','routeCautionWarnings','via','routeSnapKm'):
                s[k]=x.get(k,[] if 'Warnings' in k or k in ('routeWarnings','via') else None)
off=d.get('settlements',[])
meta=d.setdefault('meta',{})
meta['verifiedOfficialRoutes']=sum(1 for x in off if x.get('routeVerified'))
meta['cautionOfficialRoutes']=sum(1 for x in off if x.get('routeCaution'))
meta['blockedOfficialRoutes']=[x['name'] for x in off if not x.get('routeVerified')]
meta['unverifiedOfficialRoutes']=meta['blockedOfficialRoutes']
meta['safeRoutes']=sum(1 for x in points if x.get('routeVerified'))
meta['routeAuditPolicy']='hard: ford/motor-vehicle prohibition/impassable/vehicle dimensions; caution: untagged river crossing or generic access restriction'
DATA.write_text(PREFIX+json.dumps(d,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print('Verified official:',meta['verifiedOfficialRoutes'],'/ 306')
print('Caution official:',meta['cautionOfficialRoutes'])
print('Blocked official:',meta['blockedOfficialRoutes'])
print('Warning classes:',dict(counts))
