#!/usr/bin/env python3
"""Backup-first, fail-closed installer for SummitDesk v68-v72."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parent.parent
pkg = Path(__file__).resolve().parent
hub = root/'floorplans/staff_hub.py'
tmpl = root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
mod = root/'floorplans/operations_exports_v68_v72.py'
if not hub.is_file() or not tmpl.is_file() or not (root/'floorplans/manager_operations_v63_v67.py').is_file():
    sys.exit('v63-v67 Manager Operations prerequisites missing; no changes made.')
source, html = hub.read_text(), tmpl.read_text()
if mod.exists() or 'V68_V72_EXPORTS' in source or 'V68_V72_EXPORTS' in html:
    sys.exit('v68-v72 already installed or partially installed; no changes made.')
needle = """        operations = build_manager_operations(hut, selected_start)
        return render(request, 'floorplans/manager_operations_v63_v67.html', {
"""
replacement = """        operations = build_manager_operations(hut, selected_start)
        # V68_V72_EXPORTS: manager-only; reuse the hut-scoped operations dataset.
        action_level = request.GET.get('action_level', 'all')
        if action_level not in PRIORITIES:
            action_level = 'all'
        displayed_actions = filter_actions(operations['actions'], action_level)
        export_kind = request.GET.get('operations_export', '')
        if export_kind in EXPORT_TYPES:
            return operations_csv(hut, operations, export_kind, displayed_actions)
        return render(request, 'floorplans/manager_operations_v63_v67.html', {
"""
if source.count(needle) != 1:
    sys.exit('Expected v63-v67 manager-only dispatch not found uniquely; no changes made.')
context_needle = "'forecast_max': today + timedelta(days=365), 'ops': operations,"
if source.count(context_needle) != 1:
    sys.exit('Expected manager operations context not found uniquely; no changes made.')
new_source = source.replace(needle, replacement, 1).replace(context_needle,
    context_needle + "\n            'displayed_actions': displayed_actions, 'action_level': action_level,", 1)
new_source = 'from .operations_exports_v68_v72 import EXPORT_TYPES, PRIORITIES, filter_actions, operations_csv\n' + new_source
# Respect module docstrings and __future__ imports.
if new_source.startswith('from .operations_exports'):
    new_source = source.replace(needle, replacement, 1).replace(context_needle,
        context_needle + "\n            'displayed_actions': displayed_actions, 'action_level': action_level,", 1)
    tree = ast.parse(source)
    lines = new_source.splitlines(keepends=True)
    insert_at = 0
    for node in tree.body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)) or (isinstance(node, ast.ImportFrom) and node.module == '__future__'):
            insert_at = node.end_lineno
        else:
            break
    lines.insert(insert_at, 'from .operations_exports_v68_v72 import EXPORT_TYPES, PRIORITIES, filter_actions, operations_csv\n')
    new_source = ''.join(lines)
new_source = new_source.replace('operations_csv\n', 'operations_csv\n')
ast.parse(new_source)
# The new links remain within the separate page, which is only served by the manager branch.
if html.count('<h2>v63 · Reservation conflict dashboard</h2>') != 1 or html.count('<h2>v66 · Manager action center</h2>') != 1:
    sys.exit('Unexpected Manager Operations template; no changes made.')

def export_link(kind, title):
    return ("<p><a href=\"?operations=1&amp;forecast_start={{ forecast_start|date:'Y-m-d' }}"
            "&amp;action_level={{ action_level }}&amp;operations_export=" + kind + "\">" + title + "</a></p>")
new_html = html.replace('<h2>v63 · Reservation conflict dashboard</h2>',
    '<h2>v63 · Reservation conflict dashboard</h2>' + export_link('conflicts','v68 · Export conflicts CSV'),1)
new_html = new_html.replace('<h2>v64 · Room availability calendar</h2>',
    '<h2>v64 · Room availability calendar</h2>' + export_link('availability','v69 · Export availability CSV'),1)
new_html = new_html.replace('<h2>v65 · Arrival preparation board</h2>',
    '<h2>v65 · Arrival preparation board</h2>' + export_link('arrivals','v70 · Export arrivals CSV'),1)
new_html = new_html.replace('<h2>v66 · Manager action center</h2>',
    """<h2>v66 · Manager action center</h2>
<!-- V68_V72_EXPORTS -->
<form method="get" aria-label="Filter manager actions">
<input type="hidden" name="operations" value="1">
<input type="hidden" name="forecast_start" value="{{ forecast_start|date:'Y-m-d' }}">
<label for="action_level">v72 · Action priority</label>
<select id="action_level" name="action_level">
<option value="all" {% if action_level == 'all' %}selected{% endif %}>All actions</option>
<option value="conflicts" {% if action_level == 'conflicts' %}selected{% endif %}>Conflicts</option>
<option value="assignments" {% if action_level == 'assignments' %}selected{% endif %}>Bed assignments</option>
<option value="cleaning" {% if action_level == 'cleaning' %}selected{% endif %}>Cleaning</option>
</select><button type="submit">Apply</button></form>
<p class="muted">Showing {{ displayed_actions|length }} of {{ ops.action_count }} actions.</p>
""" + export_link('actions','v71 · Export displayed actions CSV'),1)
if new_html.count('{% for a in ops.actions %}') != 1:
    sys.exit('Action list loop not found uniquely; no changes made.')
new_html = new_html.replace('{% for a in ops.actions %}', '{% for a in displayed_actions %}',1)
# Keep template compatible with existing style, and make the filter accessible.
new_html = new_html.replace('input,button{font:inherit;', 'input,button,select{font:inherit;',1)
if new_html.count('V68_V72_EXPORTS') != 1:
    sys.exit('Template patch marker missing; no changes made.')
backup_stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
try:
    for file in (hub,tmpl):
        backup = file.with_name(file.name+'.bak_v68_v72_'+backup_stamp)
        shutil.copy2(file,backup)
        backups.append((file,backup))
    shutil.copy2(pkg/'operations_exports_v68_v72.py',mod)
    hub.write_text(new_source)
    tmpl.write_text(new_html)
except Exception:
    for file,backup in backups:
        shutil.copy2(backup,file)
    mod.unlink(missing_ok=True)
    raise
print('Installed v68-v72. Backups:')
for _,backup in backups:
    print(' ',backup)
print('Run Django checks and verify manager, cleaner and cross-hut permissions.')
