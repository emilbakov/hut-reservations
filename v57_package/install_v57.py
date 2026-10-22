#!/usr/bin/env python3
"""SummitDesk v57: fail-closed, backup-first search installer."""
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
module = root / 'floorplans/capacity_search_v57.py'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub files missing. No changes made.')
src = py.read_text(encoding='utf-8')
tmpl = html.read_text(encoding='utf-8')
if module.exists() or 'capacity_search_v57' in src or 'V57_CAPACITY_SEARCH' in tmpl:
    sys.exit('v57 already or partially installed. No changes made.')
if ('capacity_filters_v56' not in src or 'capacity_summary_v55' not in src
        or tmpl.count('<!-- V56_CAPACITY_FILTER_START -->') != 1
        or tmpl.count('<!-- V56_CAPACITY_FILTER_END -->') != 1
        or tmpl.count('<!-- V53_CAPACITY_WATCH_START -->') != 1
        or tmpl.count('<!-- V53_CAPACITY_WATCH_END -->') != 1):
    sys.exit('v56 prerequisites missing. No changes made.')

start = tmpl.index('<!-- V53_CAPACITY_WATCH_START -->')
end = tmpl.index('<!-- V53_CAPACITY_WATCH_END -->') + len('<!-- V53_CAPACITY_WATCH_END -->')
if end <= start:
    sys.exit('Unexpected watch marker order. No changes made.')
# Verify manager-only placement using Django template block nesting, like v56.
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

section = tmpl[start:end]
form_start = section.index('<!-- V56_CAPACITY_FILTER_START -->')
form_end = section.index('<!-- V56_CAPACITY_FILTER_END -->')
form = section[form_start:form_end]
if form.count('name="capacity_level"') != 1 or form.count('</form>') != 1:
    sys.exit('Unexpected v56 filter form. No changes made.')
field = '''  <!-- V57_CAPACITY_SEARCH -->
  <label for="v57-capacity-query">Search warnings:</label>
  <input id="v57-capacity-query" type="search" name="capacity_q" maxlength="100"
         value="{{ capacity_query_v57 }}" placeholder="Date, severity or description"
         style="padding:8px;border:1px solid #c8d7cb;border-radius:8px;max-width:260px">
'''
form = form.replace('  <button type="submit"', field + '  <button type="submit"', 1)
old_count = '{{ capacity_filtered_v56|length }} matching warning{{ capacity_filtered_v56|length|pluralize }}'
if form.count(old_count) != 1:
    sys.exit('Expected v56 count missing. No changes made.')
form = form.replace(old_count, '{{ capacity_results_v57|length }} matching warning{{ capacity_results_v57|length|pluralize }}')
section = section[:form_start] + form + section[form_end:]
loop = '{% for item in capacity_filtered_v56 %}'
if section.count(loop) != 1:
    sys.exit('Expected v56 warning loop missing. No changes made.')
section = section.replace(loop, '{% for item in capacity_results_v57 %}', 1)
newtmpl = tmpl[:start] + section + tmpl[end:]

# Find exactly one v56 context assignment, append search after it.
tree = ast.parse(src)
found = []
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Tuple) and any(
                isinstance(e, ast.Subscript) and isinstance(e.value, ast.Name)
                and e.value.id == 'context' and isinstance(e.slice, ast.Constant)
                and e.slice.value == 'capacity_filtered_v56' for e in target.elts
            ):
                found.append(node)
if len(found) != 1:
    sys.exit('Expected exactly one v56 context assignment. No changes made.')
node = found[0]
lines = src.splitlines(keepends=True)
indent = re.match(r'^\s*', lines[node.lineno - 1]).group(0)
if not indent:
    sys.exit('Expected manager-scoped assignment. No changes made.')
addition = (indent + "context['capacity_query_v57'], context['capacity_results_v57'] = search_capacity_watch(\n"
            + indent + "    context['capacity_filtered_v56'], request.GET.get('capacity_q'))\n")
lines.insert(node.end_lineno, addition)
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                                   and isinstance(first.value.value, str)) else 0
lines.insert(insert_at, 'from .capacity_search_v57 import search_capacity_watch\n')
newpy = ''.join(lines)
ast.parse(newpy)

stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
created = False
try:
    for path in (py, html):
        backup = path.with_name(path.name + '.bak_v57_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'capacity_search_v57.py', module)
    created = True
    py.write_text(newpy, encoding='utf-8')
    html.write_text(newtmpl, encoding='utf-8')
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    if created:
        module.unlink(missing_ok=True)
    raise
print('v57 installed successfully. Backups:')
for _, backup in backups:
    print(' ', backup)
print('Run Django checks and verify manager/cleaner access before restart.')
