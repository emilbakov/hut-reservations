#!/usr/bin/env python3
"""SummitDesk v45: safe, idempotent, backup-first patch for v44."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parent.parent
hub_file = root / 'floorplans/staff_hub.py'
tpl_file = root / 'floorplans/templates/floorplans/staff_hub.html'
source = Path(__file__).resolve().parent / 'forecast_dates_v45.py'
dest = root / 'floorplans/forecast_dates_v45.py'
if not all(p.is_file() for p in (hub_file, tpl_file, source)):
    sys.exit('ERROR: Required files missing. No changes made.')
hub, tpl = hub_file.read_text(), tpl_file.read_text()
if 'V45_FORECAST_DATES' in hub or 'V45_FORECAST_DATES' in tpl or dest.exists():
    sys.exit('ERROR: v45 already installed or conflicting module exists. No changes made.')
if 'V44_FORECAST_CSV' not in hub or 'V44_FORECAST_CSV' not in tpl:
    sys.exit('ERROR: Install v44 first. No changes made.')

hub_import = 'from .staff_forecast_v38 import build_forecast\n'
hub_anchor = "        context['forecast_v38'] = build_forecast(hut, today)\n"
export_anchor = "            return export_forecast_csv(hut, context['forecast_v38'])\n"
tpl_heading = '  <h2 id="v38-forecast-title">Next 7 days · Operations forecast</h2>'
tpl_loop = '{% for day in forecast_v38 %}'
tpl_export_form = '  <form method="get" action="" style="margin:12px 0">'
for label, data, anchor in [('hub import', hub, hub_import), ('forecast', hub, hub_anchor), ('export', hub, export_anchor), ('heading', tpl, tpl_heading), ('loop', tpl, tpl_loop), ('export form', tpl, tpl_export_form)]:
    if data.count(anchor) != 1:
        sys.exit(f'ERROR: Expected exactly one {label} anchor, found {data.count(anchor)}. No changes made.')

hub = hub.replace(hub_import, hub_import + 'from .forecast_dates_v45 import select_forecast_start  # V45_FORECAST_DATES\n', 1)
hub = hub.replace(hub_anchor, hub_anchor + "        # V45_FORECAST_DATES: keep today's forecast for v39-v43 alerts.\n        forecast_start = select_forecast_start(request.GET.get('forecast_start'), today)\n        context['forecast_start_v45'] = forecast_start\n        context['forecast_max_v45'] = today + timedelta(days=365)\n        context['forecast_display_v45'] = (context['forecast_v38'] if forecast_start == today\n                                           else build_forecast(hut, forecast_start))\n", 1)
hub = hub.replace(export_anchor, "            return export_forecast_csv(hut, context['forecast_display_v45'])\n", 1)
tpl = tpl.replace(tpl_heading, tpl_heading + '''
  <!-- V45_FORECAST_DATES -->
  <form method="get" action="" style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:12px 0">
    <label for="forecast-start-v45">Forecast starts</label>
    <input id="forecast-start-v45" name="forecast_start" type="date" value="{{ forecast_start_v45|date:'Y-m-d' }}" min="{{ today|date:'Y-m-d' }}" max="{{ forecast_max_v45|date:'Y-m-d' }}" required style="padding:9px;border:1px solid #b6cbbd;border-radius:8px">
    <button type="submit" style="padding:9px 14px;border:1px solid #153f34;border-radius:9px;background:#153f34;color:white;cursor:pointer">Show forecast</button>
    <a href="?" style="color:#153f34">Reset to today</a>
  </form>''', 1)
tpl = tpl.replace(tpl_loop, '{% for day in forecast_display_v45 %}', 1)
tpl = tpl.replace(tpl_export_form, tpl_export_form + '\n    <input type="hidden" name="forecast_start" value="{{ forecast_start_v45|date:\'Y-m-d\' }}">', 1)

backup = root / ('v45_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
backup.mkdir()
shutil.copy2(hub_file, backup / 'staff_hub.py')
shutil.copy2(tpl_file, backup / 'staff_hub.html')
try:
    shutil.copy2(source, dest)
    hub_file.write_text(hub)
    tpl_file.write_text(tpl)
except Exception:
    shutil.copy2(backup / 'staff_hub.py', hub_file)
    shutil.copy2(backup / 'staff_hub.html', tpl_file)
    dest.unlink(missing_ok=True)
    raise
print('SummitDesk v45 installed. Backups:', backup)
print('Next: python -m py_compile floorplans/staff_hub.py floorplans/forecast_dates_v45.py && python manage.py check')
