#!/usr/bin/env python3
"""Fail-closed, backup-first installer for v58 through v62."""
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
module = root / 'floorplans/operations_v58_v62.py'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub files missing; no changes made.')
src, tmpl = py.read_text(), html.read_text()
if module.exists() or 'V58_V62_OPERATIONS_START' in tmpl or 'operations_v58_v62' in src:
    sys.exit('Bundle already installed or partially installed; no changes made.')
if ('capacity_results_v57' not in src or 'forecast_display_v45' not in src
        or tmpl.count('<!-- V53_CAPACITY_WATCH_START -->') != 1):
    sys.exit('v57 prerequisites missing; no changes made.')
# Verify the exact insertion point is under an active {% if manager %} branch.
marker = '<!-- V53_CAPACITY_WATCH_START -->'
pos = tmpl.index(marker)
stack = []
for m in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:pos], re.S):
    tag, arg = m.group(1), m.group(2).strip()
    if tag in ('if', 'for', 'with'):
        stack.append((tag, arg))
    elif tag in ('endif', 'endfor', 'endwith'):
        expected = {'endif':'if', 'endfor':'for', 'endwith':'with'}[tag]
        if not stack or stack[-1][0] != expected:
            sys.exit('Template nesting invalid; no changes made.')
        stack.pop()
    elif tag == 'elif':
        if not stack or stack[-1][0] != 'if':
            sys.exit('Template nesting invalid; no changes made.')
        stack[-1] = ('if', arg)
    elif tag == 'else' and stack and stack[-1][0] == 'if':
        stack[-1] = ('if', 'ELSE:' + stack[-1][1])
if ('if', 'manager') not in stack:
    sys.exit('Manager-only template placement not verified; no changes made.')
# Insert v58 CSV link near v56/v57 filter form, preserving GET filters.
filter_marker = '<!-- V56_CAPACITY_FILTER_END -->'
if tmpl.count(filter_marker) != 1:
    sys.exit('Expected v56 filter marker missing; no changes made.')
link = '''<p><a class="link" style="display:inline-block" href="?forecast_start={{ forecast_start_v45|date:'Y-m-d'|urlencode }}&amp;capacity_level={{ capacity_level_v56|urlencode }}&amp;capacity_q={{ capacity_query_v57|urlencode }}&amp;capacity_filtered_export=csv">Export displayed warnings CSV (v58)</a></p>\n'''
# Resolve level from actual context tuple assignment (not guessed).
if 'capacity_level_v56' not in src:
    sys.exit('Expected v56 level context missing; no changes made.')
newtmpl = tmpl.replace(filter_marker, filter_marker + '\n' + link, 1)
newtmpl = newtmpl.replace(marker, (pkg / 'operations_fragment.html').read_text() + '\n' + marker, 1)
# Locate v57 context assignment via AST and add functionality immediately after it.
tree = ast.parse(src)
found = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        if any(isinstance(target, ast.Tuple) and any(isinstance(e, ast.Subscript)
                and isinstance(e.value, ast.Name) and e.value.id == 'context'
                and isinstance(e.slice, ast.Constant) and e.slice.value == 'capacity_results_v57'
                for e in target.elts) for target in node.targets):
            found.append(node)
if len(found) != 1:
    sys.exit('Expected exactly one v57 assignment; no changes made.')
node = found[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[node.lineno - 1]).group(0)
if len(indent) < 4:
    sys.exit('Manager-only Python branch not verified; no changes made.')
addition = (
    indent + "# V58_V62_OPERATIONS: same filtered rows for screen and CSV.\n"
    + indent + "if request.GET.get('capacity_filtered_export') == 'csv':\n"
    + indent + "    return capacity_csv(hut, context['capacity_results_v57'])\n"
    + indent + "context['room_operations_v62'] = build_room_operations(hut, context['forecast_start_v45'])\n"
)
lines.insert(node.end_lineno, addition)
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
    and isinstance(first.value.value, str)) else 0
lines.insert(insert_at, 'from .operations_v58_v62 import capacity_csv, build_room_operations\n')
newpy = ''.join(lines)
ast.parse(newpy)
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v58_v62_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'operations_v58_v62.py', module)
    py.write_text(newpy)
    html.write_text(newtmpl)
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    module.unlink(missing_ok=True)
    raise
print('v58-v62 bundle installed. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run python manage.py check and test manager and cleaner access before restart.')
