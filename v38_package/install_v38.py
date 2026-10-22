#!/usr/bin/env python3
"""SummitDesk v38 safe, idempotent patch of staff hub and template."""
from pathlib import Path
from datetime import datetime

root = Path(__file__).resolve().parent
project = Path.cwd()
view = project / 'floorplans/staff_hub.py'
template = project / 'floorplans/templates/floorplans/staff_hub.html'
for p in (view, template):
    if not p.is_file():
        raise SystemExit(f'Missing {p}; run from Django project root')
v = view.read_text()
t = template.read_text()
if 'V38_FORECAST_START' in v or 'V38_FORECAST_START' in t:
    raise SystemExit('v38 appears already installed; no changes made.')
if 'def staff_hub(request, hut_id):' not in v or "return render(request, 'floorplans/staff_hub.html', context)" not in v:
    raise SystemExit('Unexpected staff_hub.py structure; no changes made.')
if '</main></body></html>' not in t or '{% if manager %}' not in t:
    raise SystemExit('Unexpected staff_hub.html structure; no changes made.')
# Fix legacy v37 duplicate imports only if present, to avoid UnboundLocalError.
v = v.replace('        from bookings.models import ReservationItem\n', '').replace('        from django.db.models import Q\n', '')
# Forecast implementation is in a separate module; only an import and call are added.
v = v.replace('from .hut_staff import HutCleaner\n', 'from .hut_staff import HutCleaner\nfrom .staff_forecast_v38 import build_forecast\n', 1)
v = v.replace("    return render(request, 'floorplans/staff_hub.html', context)", "    # V38_FORECAST_START\n    if manager:\n        context['forecast_v38'] = build_forecast(hut, today)\n    # V38_FORECAST_END\n    return render(request, 'floorplans/staff_hub.html', context)", 1)
fragment = (root / 'forecast_fragment.html').read_text()
t = t.replace('</main></body></html>', fragment + '</main></body></html>', 1)
# Backup only after all checks pass.
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for p in (view, template):
    backup = p.with_name(p.name + f'.bak_before_v38_{stamp}')
    backup.write_bytes(p.read_bytes())
    print('Backup:', backup)
view.write_text(v)
template.write_text(t)
print('SummitDesk v38 installed. Run python manage.py check before restarting Gunicorn.')
