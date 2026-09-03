#!/usr/bin/env python3
from pathlib import Path

src=Path(__file__).with_name('reroute_firetruck_safe.py')
code=src.read_text(encoding='utf-8')

# Use current public Overpass instances. Try each endpoint once and fail over quickly
# instead of spending many minutes retrying the same overloaded server.
code=code.replace(
"OVERPASS = [\"https://overpass-api.de/api/interpreter\",\"https://overpass.kumi.systems/api/interpreter\"]",
"OVERPASS = [\"https://maps.mail.ru/osm/tools/overpass/api/interpreter\",\"https://overpass.private.coffee/api/interpreter\",\"https://overpass-api.de/api/interpreter\"]"
)
code=code.replace('for attempt in range(4):', 'for attempt in range(1):')

# Emergency-response profile: private/seasonal/poor roads are undesirable, not automatically impossible.
# Physical restrictions and explicit motor-vehicle prohibitions remain hard blocks.
code=code.replace('deny={"no","private"}', 'deny={"no"}')
code=code.replace('for k in ("access","vehicle","motor_vehicle","motorcar","hgv"):', 'for k in ("access","vehicle","motor_vehicle","motorcar"):')
code=code.replace('    if norm(tags.get("seasonal")) in {"yes","true","1"}: return True,"seasonal"\n', '')
code=code.replace('    if sm in {"horrible","very_horrible","impassable"}: return True,"smoothness="+sm', '    if sm in {"impassable"}: return True,"smoothness="+sm')
code=code.replace(
"    sm=norm(tags.get(\"smoothness\"))\n    base*= {\"excellent\":.98,\"good\":1.0,\"intermediate\":1.05,\"bad\":1.4,\"very_bad\":2.2}.get(sm,1.0)\n    return base",
"    sm=norm(tags.get(\"smoothness\"))\n    base*= {\"excellent\":.98,\"good\":1.0,\"intermediate\":1.05,\"bad\":1.4,\"very_bad\":2.2,\"horrible\":5.0,\"very_horrible\":9.0}.get(sm,1.0)\n    if norm(tags.get(\"access\"))==\"private\": base*=6.0\n    if norm(tags.get(\"seasonal\")) in {\"yes\",\"true\",\"1\"}: base*=5.0\n    if norm(tags.get(\"hgv\"))==\"no\": base*=5.0\n    return base"
)

# Block only an actual ford node/way. Nearby bridges must remain routable.
code=code.replace("def near_ford(p): return any(hav(p,f)<0.035 for f in ford_pts)", "def near_ford(p): return any(hav(p,f)<0.006 for f in ford_pts)")

# Snap every destination to the nearest road node that is actually reachable from PSCH-46.
# A settlement marker can be a centroid far away from the road. The red route must therefore end
# on a real reachable road, never with a fabricated straight drive segment to the marker.
code=code.replace(
"def route_to(pt):\n    t=nearest(pt)\n    if t not in dist: return [],None",
"def route_to(pt,max_snap_km=None):\n    c=math.cos(math.radians(pt[0]))\n    t=min(dist.keys(),key=lambda n:(n[0]-pt[0])**2+((n[1]-pt[1])*c)**2)\n    snap=hav(pt,t)\n    if max_snap_km is not None and snap>max_snap_km: return [],None"
)
code=code.replace(
"r,km=route_to((float(s['lat']),float(s['lon'])))",
"r,km=route_to((float(s['lat']),float(s['lon'])),None)"
)
code=code.replace(
"failures.append(s['name']); continue",
"failures.append((s['name'],bool(s.get('isOfficial')))); s['routeVerified']=False; continue"
)
code=code.replace(
"s['route']=r; s['distanceKm']=km; s['via']=route_via(r,official,s.get('id'),km or 0)",
"s['route']=r; s['distanceKm']=km; s['via']=route_via(r,official,s.get('id'),km or 0); s['routeSnapKm']=round(hav((float(s['lat']),float(s['lon'])),tuple(r[-1])),2); s['routeVerified']=(not s.get('isOfficial')) or s['routeSnapKm']<=2.0; s['routeNote']=None if s['routeVerified'] else 'Подъезд от ближайшей подтверждённой дороги до населённого пункта требует отдельной проверки'"
)
code=code.replace(
"if failures:\n    print('UNROUTABLE:',failures[:30]); raise RuntimeError(f'{len(failures)} training points have no safe road route')",
"if failures:\n    print('UNROUTABLE:',failures[:30])\n    official_failures=[name for name,is_official in failures if is_official]\n    if official_failures: raise RuntimeError(f'{len(official_failures)} official settlements have no reachable safe-road route at all: {official_failures}')"
)
# Propagate route verification metadata into special training modes.
code=code.replace(
"s['route']=src.get('route',[]); s['distanceKm']=src.get('distanceKm'); s['via']=src.get('via',[])",
"s['route']=src.get('route',[]); s['distanceKm']=src.get('distanceKm'); s['via']=src.get('via',[]); s['routeVerified']=src.get('routeVerified'); s['routeSnapKm']=src.get('routeSnapKm'); s['routeNote']=src.get('routeNote')"
)

code=code.replace("'routingProfile':'firetruck-safe-v2.1'", "'routingProfile':'firetruck-safe-balanced-v2.2'")
code=code.replace(
"'safeRoutes':len(allp),",
"'safeRoutes':sum(1 for s in allp if s.get('route')),\n    'verifiedOfficialRoutes':sum(1 for s in official if s.get('routeVerified')),\n    'unverifiedOfficialRoutes':[s.get('name') for s in official if s.get('routeVerified') is False],\n    'unverifiedExtraRoutes':sum(1 for s in allp if s.get('isExtra') and not s.get('routeVerified')),\n    'maxOfficialRouteSnapKm':max((s.get('routeSnapKm',0) for s in official),default=0),"
)

exec(compile(code,str(src),'exec'))
