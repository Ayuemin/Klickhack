#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "src" / "main" / "assets" / "www" / "data.js"
OUT = ROOT / "all_named_source.json"

raw = DATA.read_text(encoding="utf-8").strip()
prefix = "window.OFFLINE_DATA="
if not raw.startswith(prefix):
    raise RuntimeError("Unexpected data.js format")
body = raw[len(prefix):]
if body.endswith(";"):
    body = body[:-1]
data = json.loads(body)
places = data.get("settlements", [])
OUT.write_text(json.dumps(places, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("Captured named OSM place/locality objects:", len(places))
