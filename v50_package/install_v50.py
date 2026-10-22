#!/usr/bin/env python3
"""Backup-first v50 installer; safe to re-run (no-op if installed)."""
from datetime import datetime, timezone
from pathlib import Path
import ast
import re
import shutil
import sys

root = Path(__file__).resolve().parent.parent
pkg = Path(__file__).resolve().parent
py = root / 'floorplans/staff_hub.py'
html = root / 'floorplans/templates/floorplans/staff_hub.html'
module = root / 'floorplans/forecast_summary_v50.py'
fragment = (pkg / 'summary_fragment.html').read_text(encoding='utf-8')
if not py.exists() or not html.exists():
    sys.exit('Staff Hub files not found; no changes made.')
src = py.read_text(encoding='utf-8')
tmpl = html.read_text(encoding='utf-8')
if 'V50_FORECAST_SUMMARY_START' in tmpl or 'forecast_summary_v50' in src:
    sys.exit('v50 already installed or partially installed; no changes made.')
if 'forecast_display_v45' not in src or 'V49_OCCUPANCY_CHART_START' not in tmpl:
    sys.exit('Requires v45 forecast data and v49 chart; no changes made.')
# Find the actual AST assignment, including multiline expressions.
tree = ast.parse(src)
assignments = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Assign):
        continue
    for target in node.targets:
        if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                and target.value.id == 'context' and isinstance(target.slice, ast.Constant)
                and target.slice.value == 'forecast_display_v45'):
            assignments.append(node)
if len(assignments) != 1:
    sys.exit('Cannot locate unique v45 forecast assignment; no changes made.')
assignment = assignments[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[assignment.lineno-1]).group(0)
if not indent:
    sys.exit('Forecast assignment is not inside a manager branch; no changes made.')
addition = indent + "context['forecast_summary_v50'] = summarize_forecast(context['forecast_display_v45'])\n"
lines.insert(assignment.end_lineno, addition)
importline = 'from .forecast_summary_v50 import summarize_forecast\n'
# Insert after the module docstring, before regular imports.
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                                   and isinstance(first.value.value, str)) else 0
lines.insert(insert_at, importline)
newpy = ''.join(lines)
ast.parse(newpy)
# Insert directly before the v49 chart; inspect template conditional stack at that point.
anchor = '<!-- V49_OCCUPANCY_CHART_START -->'
if tmpl.count(anchor) != 1:
    sys.exit('v49 chart anchor not unique; no changes made.')
cut = tmpl.index(anchor)
stack = []
for m in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:cut], re.S):
    tag, args = m.group(1), m.group(2).strip()
    if tag in ('if', 'for', 'with'):
        stack.append((tag, args))
    elif tag in ('endif', 'endfor', 'endwith'):
        required = {'endif':'if','endfor':'for','endwith':'with'}[tag]
        if not stack or stack[-1][0] != required:
            sys.exit('Template block structure unexpected; no changes made.')
        stack.pop()
    elif tag == 'elif' and (not stack or stack[-1][0] != 'if'):
        sys.exit('Template elif structure unexpected; no changes made.')
if ('if', 'manager') not in stack:
    sys.exit('v49 chart is not inside an active manager-only block; no changes made.')
newtmpl = tmpl[:cut] + fragment + '\n' + tmpl[cut:]
if module.exists():
    sys.exit('v50 module already exists; no changes made.')
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v50_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'forecast_summary_v50.py', module)
    py.write_text(newpy, encoding='utf-8')
    html.write_text(newtmpl, encoding='utf-8')
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    if module.exists():
        module.unlink()
    raise
print('v50 installed. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run Django checks and verify manager/cleaner access before restarting.')
