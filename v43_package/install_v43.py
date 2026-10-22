#!/usr/bin/env python3
"""Idempotent, backup-first installer for SummitDesk v43."""
from pathlib import Path
from datetime import datetime
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / 'floorplans/staff_hub.py'
TEMPLATE = ROOT / 'floorplans/templates/floorplans/staff_hub.html'
SOURCE = Path(__file__).resolve().parent / 'alert_export_v43.py'
DEST = ROOT / 'floorplans/alert_export_v43.py'

if not all(p.is_file() for p in (HUB, TEMPLATE, SOURCE)):
    sys.exit('ERROR: required project files missing; no changes made')

hub = HUB.read_text()
html = TEMPLATE.read_text()
if 'V43_CSV_EXPORT' in hub or 'V43_CSV_EXPORT' in html:
    sys.exit('ERROR: v43 marker already present; no changes made')
if "from .alert_search_v42 import search_alerts" not in hub or "context['alert_search_v42'] = search_alerts" not in hub:
    sys.exit('ERROR: v42 integration not found; no changes made')
if '  <!-- V42_ALERT_SEARCH_START -->' not in html or '  <!-- V42_ALERT_SEARCH_END -->' not in html:
    sys.exit('ERROR: v42 template anchors not found; no changes made')
if DEST.exists():
    sys.exit('ERROR: alert_export_v43.py already exists; no changes made')

hub_import = 'from .alert_search_v42 import search_alerts\n'
hub = hub.replace(hub_import, hub_import + 'from .alert_export_v43 import export_alerts_csv  # V43_CSV_EXPORT\n', 1)
anchor = "        context['alert_search_v42'] = search_alerts(context['alert_filter_v41'], request.GET.get('alert_q', ''))\n"
if hub.count(anchor) != 1:
    sys.exit('ERROR: expected v42 assignment exactly once; no changes made')
hub = hub.replace(anchor, anchor + "        # V43_CSV_EXPORT: only managers reach this branch; reuse displayed filtered rows.\n        if request.GET.get('alert_export') == 'csv':\n            return export_alerts_csv(hut, context['alert_search_v42']['rows'])\n", 1)

# A second GET form preserves the current severity and query values without JS.
needle = '  <!-- V42_ALERT_SEARCH_END -->'
if html.count(needle) != 1:
    sys.exit('ERROR: unexpected template structure; no changes made')
# Add export button to the existing GET form so current filter/search inputs are submitted together.
submit = '  <button type="submit" style="padding:9px 15px;border:0;border-radius:9px;background:#153f34;color:white;cursor:pointer">Apply filter</button>'
if html.count(submit) != 1:
    sys.exit('ERROR: filter submit button not found; no changes made')
html = html.replace(submit, submit + '\n  <!-- V43_CSV_EXPORT -->\n  <button type="submit" name="alert_export" value="csv" style="padding:9px 15px;border:1px solid #153f34;border-radius:9px;background:white;color:#153f34;cursor:pointer">Export filtered CSV</button>', 1)

stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup = ROOT / f'v43_backup_{stamp}'
backup.mkdir()
shutil.copy2(HUB, backup / 'staff_hub.py')
shutil.copy2(TEMPLATE, backup / 'staff_hub.html')
try:
    shutil.copy2(SOURCE, DEST)
    HUB.write_text(hub)
    TEMPLATE.write_text(html)
except Exception:
    shutil.copy2(backup / 'staff_hub.py', HUB)
    shutil.copy2(backup / 'staff_hub.html', TEMPLATE)
    DEST.unlink(missing_ok=True)
    raise
print('SummitDesk v43 installed. Backups:', backup)
print('Next: python -m py_compile floorplans/staff_hub.py floorplans/alert_export_v43.py && python manage.py check')
