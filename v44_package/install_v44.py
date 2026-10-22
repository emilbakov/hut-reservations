#!/usr/bin/env python3
"""Backup-first, idempotent SummitDesk v44 installer. Run from project root."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parent.parent
hub_path = root / 'floorplans/staff_hub.py'
tpl_path = root / 'floorplans/templates/floorplans/staff_hub.html'
source = Path(__file__).resolve().parent / 'forecast_export_v44.py'
dest = root / 'floorplans/forecast_export_v44.py'
if not all(p.is_file() for p in (hub_path, tpl_path, source)):
    sys.exit('ERROR: Required files missing. No changes made.')
hub, tpl = hub_path.read_text(), tpl_path.read_text()
if 'V44_FORECAST_CSV' in hub or 'V44_FORECAST_CSV' in tpl or dest.exists():
    sys.exit('ERROR: v44 appears installed or destination exists. No changes made.')
if 'V43_CSV_EXPORT' not in hub or 'V43_CSV_EXPORT' not in tpl:
    sys.exit('ERROR: v43 must be installed first. No changes made.')
import_anchor = 'from .staff_forecast_v38 import build_forecast\n'
forecast_anchor = "        context['forecast_v38'] = build_forecast(hut, today)\n"
tpl_anchor = '  <h2 id="v38-forecast-title">Next 7 days · Operations forecast</h2>'
for name, content, anchor in [('hub import', hub, import_anchor), ('forecast', hub, forecast_anchor), ('template', tpl, tpl_anchor)]:
    if content.count(anchor) != 1:
        sys.exit(f'ERROR: Expected one {name} anchor, found {content.count(anchor)}. No changes made.')
hub = hub.replace(import_anchor, import_anchor + 'from .forecast_export_v44 import export_forecast_csv  # V44_FORECAST_CSV\n', 1)
hub = hub.replace(forecast_anchor, forecast_anchor + "        # V44_FORECAST_CSV: only accessible inside the manager-only branch.\n        if request.GET.get('forecast_export') == 'csv':\n            return export_forecast_csv(hut, context['forecast_v38'])\n", 1)
tpl = tpl.replace(tpl_anchor, tpl_anchor + '\n  <!-- V44_FORECAST_CSV -->\n  <form method="get" action="" style="margin:12px 0">\n    <button type="submit" name="forecast_export" value="csv" style="padding:10px 16px;border:1px solid #153f34;border-radius:9px;background:white;color:#153f34;cursor:pointer">Export 7-day forecast CSV</button>\n  </form>', 1)
backup = root / ('v44_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
backup.mkdir()
shutil.copy2(hub_path, backup / 'staff_hub.py')
shutil.copy2(tpl_path, backup / 'staff_hub.html')
try:
    shutil.copy2(source, dest)
    hub_path.write_text(hub)
    tpl_path.write_text(tpl)
except Exception:
    shutil.copy2(backup / 'staff_hub.py', hub_path)
    shutil.copy2(backup / 'staff_hub.html', tpl_path)
    dest.unlink(missing_ok=True)
    raise
print('SummitDesk v44 installed. Backups:', backup)
print('Next: python -m py_compile floorplans/staff_hub.py floorplans/forecast_export_v44.py && python manage.py check')
