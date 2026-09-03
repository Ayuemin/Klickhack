#!/usr/bin/env python3
from pathlib import Path

src=Path(__file__).with_name('reroute_firetruck_safe.py')
code=src.read_text(encoding='utf-8')

# Emergency-response profile: private/seasonal/poor roads are undesirable, not automatically impossible.
# Physical restrictions and explicit motor-vehicle prohibitions remain hard blocks.
code=code.replace('deny={"no","private"}', 'deny={"no"}')
code=code.replace('for k in ("access","vehicle","motor_vehicle","motorcar","hgv"):', 'for k in ("access","vehicle","motor_vehicle","motorcar"):')
code=code.replace('    if norm(tags.get("seasonal")) in {"yes","true","1"}: return True,"seasonal"\n', '')
code=code.replace('    if sm in {"horrible","very_horrible","impassable"}: return True,"smoothness="+sm', '    if sm in {"impassable"}: return True,"smoothness="+sm')
code=code.replace("    sm=norm(tags.get(\"smoothness\"))\n    base*= {\"excellent\":.98,\"good\":1.0,\"intermediate\":1.05,\"bad\":1.4,\"very_bad\":2.2}.get(sm,1.0)\n    return base", "    sm=norm(tags.get(\"smoothness\"))\n    base*= {\"excellent\":.98,\"good\":1.0,\"intermediate\":1.05,\"bad\":1.4,\"very_bad\":2.2,\"horrible\":5.0,\"very_horrible\":9.0}.get(sm,1.0)\n    if norm(tags.get(\"access\"))==\"private\": base*=6.0\n    if norm(tags.get(\"seasonal\")) in {\"yes\",\"true\",\"1\"}: base*=5.0\n    if norm(tags.get(\"hgv\"))==\"no\": base*=5.0\n    return base")
# Block the exact ford node, not every road within a 35 m halo around it.
code=code.replace("def near_ford(p): return any(hav(p,f)<0.035 for f in ford_pts)", "def near_ford(p): return any(hav(p,f)<0.006 for f in ford_pts)")
code=code.replace("'routingProfile':'firetruck-safe-v2.1'", "'routingProfile':'firetruck-safe-balanced-v2.1'")

exec(compile(code,str(src),'exec'))
