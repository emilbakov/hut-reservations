#!/usr/bin/env python3
"""Install SummitDesk v41 from the Django project root; backups and preflight."""
from pathlib import Path
from datetime import datetime
import ast
import shutil

root = Path(__file__).resolve().parent
project = Path.cwd()
view = project / 'floorplans/staff_hub.py'
template = project / 'floorplans/templates/floorplans/staff_hub.html'
module = project / 'floorplans/alert_filters_v41.py'
for p in (view, template, project / 'floorplans/alert_summary_v40.py', project / 'floorplans/staff_alerts_v39.py'):
    if not p.is_file():
        raise SystemExit(f'Missing prerequisite: {p}; no changes made.')
v = view.read_text()
t = template.read_text()
if 'V41_ALERT_FILTERS_START' in t or 'alert_filters_v41' in v:
    raise SystemExit('v41 appears already installed; no changes made.')
import_needle = 'from .alert_summary_v40 import summarize_alerts'
context_needle = "        context['alert_summary_v40'] = summarize_alerts(context['alerts_v39'])"
loop_needle = '{% for alert in alerts_v39 %}'
section_needle = '<!-- V39_ALERTS_START -->'
for needle, content in ((import_needle,v),(context_needle,v),(loop_needle,t),(section_needle,t)):
    if content.count(needle) != 1:
        raise SystemExit(f'Unexpected v40 layout for {needle!r}; no changes made.')
v = v.replace(import_needle, import_needle + '\nfrom .alert_filters_v41 import filter_alerts', 1)
v = v.replace(context_needle, context_needle + "\n        # V41_ALERT_FILTERS_START\n        context['alert_filter_v41'] = filter_alerts(context['alerts_v39'], request.GET.get('alert_level', 'all'))\n        # V41_ALERT_FILTERS_END", 1)
t = t.replace(loop_needle, (root / 'filters_fragment.html').read_text() + '\n  {% for alert in alert_filter_v41.rows %}', 1)
t = t.replace('No operational alerts for the next seven days.', 'No alerts match this severity filter for the next seven days.', 1)
ast.parse(v)
ast.parse((root / 'alert_filters_v41.py').read_text())
# Complete all checks before writing, then back up touched files.
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for p in (view, template, module):
    if p.exists():
        backup = p.with_name(p.name + f'.bak_before_v41_{stamp}')
        shutil.copy2(p, backup)
        print('Backup:', backup)
shutil.copy2(root / 'alert_filters_v41.py', module)
view.write_text(v)
template.write_text(t)
print('SummitDesk v41 installed. Run Django checks before restarting Gunicorn.')
