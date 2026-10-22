#!/usr/bin/env python3
"""Backup-first, idempotent v39 installer; run from Django project root."""
from pathlib import Path
from datetime import datetime
import ast

root = Path(__file__).resolve().parent
project = Path.cwd()
view = project / 'floorplans/staff_hub.py'
template = project / 'floorplans/templates/floorplans/staff_hub.html'
module_src = root / 'staff_alerts_v39.py'
module_dst = project / 'floorplans/staff_alerts_v39.py'
for p in (view, template, project / 'floorplans/staff_forecast_v38.py'):
    if not p.is_file():
        raise SystemExit(f'Missing prerequisite: {p}. No changes made.')
v, t = view.read_text(), template.read_text()
if 'V39_ALERTS_START' in t or 'V39_ALERTS_START' in v or 'from .staff_alerts_v39 import build_alerts' in v:
    raise SystemExit('v39 appears already installed. No changes made.')
needle = "        context['forecast_v38'] = build_forecast(hut, today)"
render = "    return render(request, 'floorplans/staff_hub.html', context)"
if v.count(needle) != 1 or v.count(render) != 1 or t.count('</main></body></html>') != 1:
    raise SystemExit('Unexpected v38 layout; no changes made. Send staff_hub.py for review.')
if 'from .staff_forecast_v38 import build_forecast' not in v:
    raise SystemExit('v38 import not found; no changes made.')
v = v.replace('from .staff_forecast_v38 import build_forecast', 'from .staff_forecast_v38 import build_forecast\nfrom .staff_alerts_v39 import build_alerts', 1)
v = v.replace(needle, needle + "\n        # V39_ALERTS_START\n        context['alerts_v39'] = build_alerts(hut, today, context['forecast_v38'])\n        # V39_ALERTS_END", 1)
t = t.replace('</main></body></html>', (root / 'alerts_fragment.html').read_text() + '</main></body></html>', 1)
ast.parse(v)
ast.parse(module_src.read_text())
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for p in (view, template, module_dst):
    if p.exists():
        backup = p.with_name(p.name + f'.bak_before_v39_{stamp}')
        backup.write_bytes(p.read_bytes())
        print('Backup:', backup)
module_dst.write_bytes(module_src.read_bytes())
view.write_text(v)
template.write_text(t)
print('SummitDesk v39 installed. Run Django checks and restart Gunicorn.')
