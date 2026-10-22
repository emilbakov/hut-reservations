#!/usr/bin/env python3
"""SummitDesk v53: backup-first and fail-closed install."""
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
module = root / 'floorplans/forecast_watch_v53.py'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub files not found. No changes made.')
src, tmpl = py.read_text(encoding='utf-8'), html.read_text(encoding='utf-8')
if 'forecast_watch_v53' in src or 'V53_CAPACITY_WATCH_START' in tmpl or module.exists():
    sys.exit('v53 already installed or partially installed. No changes made.')
if 'forecast_peaks_v52' not in src or tmpl.count('<!-- V52_FORECAST_PEAKS_START -->') != 1:
    sys.exit('v52 is required. No changes made.')
cut = tmpl.index('<!-- V52_FORECAST_PEAKS_START -->')
stack = []
for m in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:cut], re.S):
    tag, args = m.group(1), m.group(2).strip()
    if tag in ('if', 'for', 'with'):
        stack.append((tag, args))
    elif tag in ('endif', 'endfor', 'endwith'):
        required = {'endif': 'if', 'endfor': 'for', 'endwith': 'with'}[tag]
        if not stack or stack[-1][0] != required:
            sys.exit('Unexpected template nesting. No changes made.')
        stack.pop()
    elif tag == 'elif':
        if not stack or stack[-1][0] != 'if':
            sys.exit('Unexpected template elif. No changes made.')
        stack[-1] = ('if', args)
    elif tag == 'else' and stack and stack[-1][0] == 'if':
        stack[-1] = ('if', 'ELSE:' + stack[-1][1])
if ('if', 'manager') not in stack:
    sys.exit('Manager-only placement could not be verified. No changes made.')
newtmpl = tmpl[:cut] + (pkg / 'watch_fragment.html').read_text(encoding='utf-8') + '\n' + tmpl[cut:]
tree = ast.parse(src)
found = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                and target.value.id == 'context' and isinstance(target.slice, ast.Constant)
                and target.slice.value == 'forecast_peaks_v52'):
                found.append(node)
if len(found) != 1:
    sys.exit('Expected one v52 context assignment. No changes made.')
node = found[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[node.lineno - 1]).group(0)
if not indent or 'forecast_display_v45' not in src:
    sys.exit('Expected manager-scoped forecast context missing. No changes made.')
lines.insert(node.end_lineno, indent + "context['forecast_watch_v53'] = build_capacity_watch(context['forecast_display_v45'])\n")
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                                   and isinstance(first.value.value, str)) else 0
lines.insert(insert_at, 'from .forecast_watch_v53 import build_capacity_watch\n')
newpy = ''.join(lines)
ast.parse(newpy)
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v53_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'forecast_watch_v53.py', module)
    py.write_text(newpy, encoding='utf-8')
    html.write_text(newtmpl, encoding='utf-8')
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    if module.exists():
        module.unlink()
    raise
print('v53 installed. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run Django checks and test manager/cleaner permissions before restarting.')
