#!/usr/bin/env python3
"""SummitDesk v54: fail-closed, backup-first capacity watch CSV installation."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import sys

root = Path(__file__).resolve().parent.parent
pkg = Path(__file__).resolve().parent
py = root / 'floorplans/staff_hub.py'
html = root / 'floorplans/templates/floorplans/staff_hub.html'
module = root / 'floorplans/capacity_export_v54.py'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub files not found. No changes made.')
src = py.read_text(encoding='utf-8')
tmpl = html.read_text(encoding='utf-8')
if 'capacity_export_v54' in src or 'V54_CAPACITY_EXPORT' in tmpl or module.exists():
    sys.exit('v54 already installed or partially installed. No changes made.')
if 'forecast_watch_v53' not in src or tmpl.count('<!-- V53_CAPACITY_WATCH_START -->') != 1:
    sys.exit('v53 is required. No changes made.')

# Verify the actual Django template block enclosing v53 is manager-only.
cut = tmpl.index('<!-- V53_CAPACITY_WATCH_START -->')
stack = []
for m in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:cut], re.S):
    tag, args = m.group(1), m.group(2).strip()
    if tag in ('if', 'for', 'with'):
        stack.append((tag, args))
    elif tag in ('endif', 'endfor', 'endwith'):
        expected = {'endif': 'if', 'endfor': 'for', 'endwith': 'with'}[tag]
        if not stack or stack[-1][0] != expected:
            sys.exit('Unexpected template nesting. No changes made.')
        stack.pop()
    elif tag == 'elif':
        if not stack or stack[-1][0] != 'if':
            sys.exit('Unexpected template nesting. No changes made.')
        stack[-1] = ('if', args)
    elif tag == 'else' and stack and stack[-1][0] == 'if':
        stack[-1] = ('if', 'ELSE:' + stack[-1][1])
if ('if', 'manager') not in stack:
    sys.exit('Manager-only placement could not be verified. No changes made.')

# Link keeps the existing forecast_start, not alert filters.
anchor = '<h2 id="v53-watch-title">Forecast capacity watch · Selected 7 days</h2>'
if tmpl.count(anchor) != 1:
    sys.exit('Expected v53 heading not found exactly once. No changes made.')
newtmpl = tmpl.replace(anchor, anchor + '\n  <!-- V54_CAPACITY_EXPORT -->\n  <p><a class="link" href="?forecast_start={{ forecast_start_v45|date:\"Y-m-d\" }}&amp;capacity_watch_export=csv">Export capacity warnings CSV<span>Selected seven days · manager only</span></a></p>', 1)
# Avoid reliance on a context variable name: use request.GET value if present? The v45
# selected start is already normalized in forecast_display_v45[0]['day']; expose a new context variable.
newtmpl = newtmpl.replace('{{ forecast_start_v45|date:"Y-m-d" }}', '{{ capacity_export_start_v54|date:"Y-m-d" }}')

tree = ast.parse(src)
found = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                and target.value.id == 'context' and isinstance(target.slice, ast.Constant)
                and target.slice.value == 'forecast_watch_v53'):
                found.append(node)
if len(found) != 1:
    sys.exit('Expected exactly one v53 context assignment. No changes made.')
node = found[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[node.lineno - 1]).group(0)
if not indent or 'forecast_display_v45' not in src:
    sys.exit('Expected forecast context not found. No changes made.')
# Guard ensures no export occurs before the existing manager access check.
addition = (
    indent + "context['capacity_export_start_v54'] = context['forecast_display_v45'][0]['day']\n"
    + indent + "if request.GET.get('capacity_watch_export') == 'csv':\n"
    + indent + "    return export_capacity_watch_csv(hut, context['forecast_watch_v53'], context['capacity_export_start_v54'])\n"
)
lines.insert(node.end_lineno, addition)
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                                   and isinstance(first.value.value, str)) else 0
lines.insert(insert_at, 'from .capacity_export_v54 import export_capacity_watch_csv\n')
newpy = ''.join(lines)
ast.parse(newpy)

stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
created = False
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v54_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'capacity_export_v54.py', module)
    created = True
    py.write_text(newpy, encoding='utf-8')
    html.write_text(newtmpl, encoding='utf-8')
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    if created:
        module.unlink(missing_ok=True)
    raise
print('v54 installed. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run Django checks and test manager/cleaner permissions before restarting.')
