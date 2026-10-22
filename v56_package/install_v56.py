#!/usr/bin/env python3
"""SummitDesk v56: backup-first, fail-closed capacity severity filter installer."""
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
module = root / 'floorplans/capacity_filters_v56.py'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub files missing. No changes made.')
src = py.read_text(encoding='utf-8')
tmpl = html.read_text(encoding='utf-8')
if module.exists() or 'capacity_filters_v56' in src or 'V56_CAPACITY_FILTER_START' in tmpl:
    sys.exit('v56 already or partially installed. No changes made.')
if ('capacity_summary_v55' not in src or 'capacity_export_v54' not in src
        or tmpl.count('<!-- V53_CAPACITY_WATCH_START -->') != 1
        or tmpl.count('<!-- V55_CAPACITY_SUMMARY_START -->') != 1):
    sys.exit('v55 prerequisites not found. No changes made.')

# Validate that the entire capacity watch section is inside the manager branch.
start = tmpl.index('<!-- V53_CAPACITY_WATCH_START -->')
end_marker = '<!-- V53_CAPACITY_WATCH_END -->'
if tmpl.count(end_marker) != 1:
    sys.exit('v53 watch end marker missing. No changes made.')
end = tmpl.index(end_marker) + len(end_marker)
stack = []
for m in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:end], re.S):
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

# Only replace the v53 loop in its own bounded section, not any other dashboard loop.
section = tmpl[start:end]
loop = '{% for item in forecast_watch_v53 %}'
if section.count(loop) != 1:
    sys.exit('Expected capacity watch loop missing. No changes made.')
section = section.replace(loop, '{% for item in capacity_filtered_v56 %}', 1)
heading = '<h2 id="v53-watch-title">Forecast capacity watch · Selected 7 days</h2>'
if section.count(heading) != 1:
    sys.exit('Capacity watch heading missing. No changes made.')
fragment = (pkg / 'filter_fragment.html').read_text(encoding='utf-8')
section = section.replace(heading, heading + '\n' + fragment, 1)
newtmpl = tmpl[:start] + section + tmpl[end:]

# Insert context assignments immediately after the original watch assignment.
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
    sys.exit('Expected exactly one watch context assignment. No changes made.')
node = found[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[node.lineno - 1]).group(0)
if not indent:
    sys.exit('Expected manager-scoped assignment. No changes made.')
# Add assignments after the v53 assignment. v54/v55 continue using original unfiltered list.
addition = (
    indent + "context['capacity_level_v56'], context['capacity_filtered_v56'] = filter_capacity_watch(\n"
    + indent + "    context['forecast_watch_v53'], request.GET.get('capacity_level'))\n"
)
lines.insert(node.end_lineno, addition)
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                                   and isinstance(first.value.value, str)) else 0
lines.insert(insert_at, 'from .capacity_filters_v56 import filter_capacity_watch\n')
newpy = ''.join(lines)
ast.parse(newpy)

stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
created = False
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v56_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'capacity_filters_v56.py', module)
    created = True
    py.write_text(newpy, encoding='utf-8')
    html.write_text(newtmpl, encoding='utf-8')
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    if created:
        module.unlink(missing_ok=True)
    raise
print('v56 installed successfully. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run Django checks and verify manager/cleaner access before restart.')
