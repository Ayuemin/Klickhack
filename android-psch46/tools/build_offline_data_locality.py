#!/usr/bin/env python3
from pathlib import Path
src = Path(__file__).with_name('build_offline_data.py')
code = src.read_text(encoding='utf-8')
code = code.replace('town|village|hamlet|isolated_dwelling', 'town|village|hamlet|isolated_dwelling|locality')
exec(compile(code, str(src), 'exec'))
