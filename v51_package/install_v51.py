#!/usr/bin/env python3
"""Backup-first, fail-closed v51 installer. Run from project root."""
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
module = root / 'floorplans/forecast_utilization_v51.py'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub source files not found. No changes made.')
src, tmpl = py.read_text(encoding='utf-8'), html.read_text(encoding='utf-8')
if 'V51_UTILIZATION_START' in tmpl or 'forecast_utilization_v51' in src or module.exists():
    sys.exit('v51 already installed or partially installed. No changes made.')
if 'V50_FORECAST_SUMMARY_START' not in tmpl or 'forecast_summary_v50' not in src:
    sys.exit('v50 is required. No changes made.')
anchor = '<!-- V50_FORECAST_SUMMARY_START -->'
if tmpl.count(anchor) != 1:
    sys.exit('v50 summary anchor missing or duplicated. No changes made.')
# Confirm manager guard is active at insertion point (handles nested if/for/with).
cut = tmpl.index(anchor)
stack = []
for match in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:cut], re.S):
    tag, args = match.group(1), match.group(2).strip()
    if tag in ('if', 'for', 'with'):
        stack.append((tag, args))
    elif tag in ('endif', 'endfor', 'endwith'):
        required = {'endif':'if','endfor':'for','endwith':'with'}[tag]
        if not stack or stack[-1][0] != required:
            sys.exit('Unexpected template nesting. No changes made.')
        stack.pop()
    elif tag == 'elif':
        if not stack or stack[-1][0] != 'if':
            sys.exit('Unexpected elif. No changes made.')
        stack[-1] = ('if', args)
    elif tag == 'else' and stack and stack[-1][0] == 'if':
        stack[-1] = ('if', 'ELSE:' + stack[-1][1])
if ('if', 'manager') not in stack:
    sys.exit('Manager-only placement could not be verified. No changes made.')
fragment = (pkg / 'utilization_fragment.html').read_text(encoding='utf-8')
newtmpl = tmpl[:cut] + fragment + '\n' + tmpl[cut:]
# AST find exact v50 summary context assignment and add adjacent assignment.
tree = ast.parse(src)
found = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                and target.value.id == 'context' and isinstance(target.slice, ast.Constant)
                and target.slice.value == 'forecast_summary_v50'):
                found.append(node)
if len(found) != 1:
    sys.exit('Expected one v50 context assignment. No changes made.')
node = found[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[node.lineno-1]).group(0)
if not indent or 'forecast_display_v45' not in src:
    sys.exit('Expected manager-scoped v45 forecast context missing. No changes made.')
lines.insert(node.end_lineno, indent + "context['forecast_utilization_v51'] = summarize_utilization(context['forecast_display_v45'])\n")
# Put module import at file level, not inside function (avoids v37 UnboundLocalError).
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                                   and isinstance(first.value.value, str)) else 0
lines.insert(insert_at, 'from .forecast_utilization_v51 import summarize_utilization\n')
newpy = ''.join(lines)
ast.parse(newpy)
# All checks completed before any writes.
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v51_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'forecast_utilization_v51.py', module)
    py.write_text(newpy, encoding='utf-8')
    html.write_text(newtmpl, encoding='utf-8')
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    if module.exists():
        module.unlink()
    raise
print('v51 installed. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run Django checks and verify manager/cleaner permissions before restarting.')
