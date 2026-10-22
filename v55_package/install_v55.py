#!/usr/bin/env python3
"""Fail-closed, backup-first SummitDesk v55 installer."""
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
module = root / 'floorplans/capacity_summary_v55.py'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub files missing. No changes made.')
src = py.read_text(encoding='utf-8')
tmpl = html.read_text(encoding='utf-8')
if module.exists() or 'capacity_summary_v55' in src or 'V55_CAPACITY_SUMMARY_START' in tmpl:
    sys.exit('v55 is already installed or partially installed. No changes made.')
if 'capacity_export_v54' not in src or tmpl.count('<!-- V53_CAPACITY_WATCH_START -->') != 1 or 'V54_CAPACITY_EXPORT' not in tmpl:
    sys.exit('v54 is required. No changes made.')

# Confirm v53 insertion point is nested in the manager-only branch.
cut = tmpl.index('<!-- V53_CAPACITY_WATCH_START -->')
stack = []
for m in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:cut], re.S):
    tag, args = m.group(1), m.group(2).strip()
    if tag in ('if', 'for', 'with'):
        stack.append((tag, args))
    elif tag in ('endif', 'endfor', 'endwith'):
        expected = {'endif':'if', 'endfor':'for', 'endwith':'with'}[tag]
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

# Place summary immediately before the existing capacity watch panel.
newtmpl = tmpl.replace('<!-- V53_CAPACITY_WATCH_START -->',
                       (pkg / 'summary_fragment.html').read_text(encoding='utf-8') + '\n<!-- V53_CAPACITY_WATCH_START -->', 1)
tree = ast.parse(src)
assignments = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                and target.value.id == 'context' and isinstance(target.slice, ast.Constant)
                and target.slice.value == 'forecast_watch_v53'):
                assignments.append(node)
if len(assignments) != 1:
    sys.exit('Expected one v53 watch context assignment. No changes made.')
node = assignments[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[node.lineno-1]).group(0)
if not indent:
    sys.exit('Expected indented manager-only context assignment. No changes made.')
lines.insert(node.end_lineno, indent + "context['capacity_summary_v55'] = summarize_capacity_watch(context['forecast_watch_v53'])\n")
first = tree.body[0]
import_line = 'from .capacity_summary_v55 import summarize_capacity_watch\n'
if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
    lines.insert(first.end_lineno, import_line)
else:
    lines.insert(0, import_line)
newpy = ''.join(lines)
ast.parse(newpy)

stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
created = False
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v55_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'capacity_summary_v55.py', module)
    created = True
    py.write_text(newpy, encoding='utf-8')
    html.write_text(newtmpl, encoding='utf-8')
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    if created:
        module.unlink(missing_ok=True)
    raise
print('v55 installed successfully. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run Django checks and verify manager/cleaner access before restart.')
