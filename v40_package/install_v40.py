#!/usr/bin/env python3
"""Backup-first, idempotent SummitDesk v40 installer. Run from project root."""
from pathlib import Path
from datetime import datetime
import ast

project = Path.cwd()
source = Path(__file__).resolve().parent
view = project / 'floorplans/staff_hub.py'
template = project / 'floorplans/templates/floorplans/staff_hub.html'
module = project / 'floorplans/alert_summary_v40.py'
for path in (view, template, project / 'floorplans/staff_alerts_v39.py'):
    if not path.is_file():
        raise SystemExit(f'Missing v39 prerequisite: {path}; no changes made.')
v = view.read_text()
t = template.read_text()
if 'V40_ALERT_SUMMARY_START' in t or 'alert_summary_v40' in v:
    raise SystemExit('v40 already installed; no changes made.')
import_needle = 'from .staff_alerts_v39 import build_alerts'
context_needle = "        context['alerts_v39'] = build_alerts(hut, today, context['forecast_v38'])"
template_needle = '<!-- V39_ALERTS_START -->'
for needle, content in ((import_needle, v), (context_needle, v), (template_needle, t)):
    if content.count(needle) != 1:
        raise SystemExit(f'Unexpected v39 layout: {needle}; no changes made.')
v = v.replace(import_needle, import_needle + '\nfrom .alert_summary_v40 import summarize_alerts', 1)
v = v.replace(context_needle, context_needle + "\n        # V40_ALERT_SUMMARY_START\n        context['alert_summary_v40'] = summarize_alerts(context['alerts_v39'])\n        # V40_ALERT_SUMMARY_END", 1)
t = t.replace(template_needle, (source / 'summary_fragment.html').read_text() + '\n' + template_needle, 1)
ast.parse(v)
ast.parse((source / 'alert_summary_v40.py').read_text())
# Back up all touched existing files before any writes.
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for path in (view, template, module):
    if path.exists():
        backup = path.with_name(path.name + f'.bak_before_v40_{stamp}')
        backup.write_bytes(path.read_bytes())
        print('Backup:', backup)
module.write_bytes((source / 'alert_summary_v40.py').read_bytes())
view.write_text(v)
template.write_text(t)
print('SummitDesk v40 installed. Run Django checks before restarting Gunicorn.')
