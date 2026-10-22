#!/usr/bin/env python3
"""SummitDesk v42 installer. Run from Django project root."""
from pathlib import Path
from datetime import datetime
import ast
import shutil

package = Path(__file__).resolve().parent
project = Path.cwd()
view = project / 'floorplans/staff_hub.py'
template = project / 'floorplans/templates/floorplans/staff_hub.html'
module = project / 'floorplans/alert_search_v42.py'
prerequisites = (view, template, project / 'floorplans/alert_filters_v41.py')
for path in prerequisites:
    if not path.is_file():
        raise SystemExit(f'Missing prerequisite: {path}. No changes made.')
v = view.read_text()
t = template.read_text()
if 'V42_ALERT_SEARCH' in v or 'V42_ALERT_SEARCH' in t:
    raise SystemExit('v42 appears already installed. No changes made.')
view_anchor = "        context['alert_filter_v41'] = filter_alerts(context['alerts_v39'], request.GET.get('alert_level', 'all'))"
import_anchor = 'from .alert_filters_v41 import filter_alerts'
template_anchor = '{% for alert in alert_filter_v41.rows %}'
form_anchor = '<!-- V41_ALERT_FILTERS_END -->'
count_anchor = 'Showing {{ alert_filter_v41.shown }} of {{ alert_filter_v41.total }} alerts'
for needle, content in ((view_anchor,v), (import_anchor,v), (template_anchor,t), (form_anchor,t), (count_anchor,t)):
    if content.count(needle) != 1:
        raise SystemExit(f'Expected v41 anchor not found exactly once: {needle}. No changes made.')
v = v.replace(import_anchor, import_anchor + '\nfrom .alert_search_v42 import search_alerts', 1)
v = v.replace(view_anchor, view_anchor + "\n        # V42_ALERT_SEARCH\n        context['alert_search_v42'] = search_alerts(context['alert_filter_v41'], request.GET.get('alert_q', ''))", 1)
t = t.replace(template_anchor, '{% for alert in alert_search_v42.rows %}', 1)
t = t.replace(count_anchor, 'Showing {{ alert_search_v42.shown }} of {{ alert_search_v42.total }} alerts', 1)
# Put keyword input inside existing GET form, so severity and keyword filters combine.
search_field = """<!-- V42_ALERT_SEARCH_START -->
  <label for="v42-alert-q" class="muted">Search alerts</label>
  <input id="v42-alert-q" type="search" name="alert_q" value="{{ alert_search_v42.query }}" maxlength="100" placeholder="Title or description" style="padding:9px;border:1px solid #dce7dc;border-radius:9px;max-width:240px;width:100%">
  <!-- V42_ALERT_SEARCH_END -->"""
# Insert directly before existing submit button, only in v41 filter form.
button = '<button type="submit" style="padding:9px 15px;border:0;border-radius:9px;background:#153f34;color:white;cursor:pointer">Apply filter</button>'
if t.count(button) != 1:
    raise SystemExit('v41 filter submit button missing or duplicated. No changes made.')
t = t.replace(button, search_field + '\n  ' + button, 1)
ast.parse(v)
ast.parse((package / 'alert_search_v42.py').read_text())
# Ensure template still has manager-gated v39 alerts section.
if '{% if manager %}' not in t or '<!-- V39_ALERTS_START -->' not in t:
    raise SystemExit('Manager-gated alert section not found. No changes made.')
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for path in (view, template, module):
    if path.exists():
        backup = path.with_name(path.name + f'.bak_before_v42_{stamp}')
        shutil.copy2(path, backup)
        print('Backup:', backup)
shutil.copy2(package / 'alert_search_v42.py', module)
view.write_text(v)
template.write_text(t)
print('SummitDesk v42 installed. Run Django checks before restarting Gunicorn.')
