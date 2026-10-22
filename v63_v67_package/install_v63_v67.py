#!/usr/bin/env python3
"""Backup-first installer for the v63-v67 manager operations page."""
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
new_module = root / 'floorplans/manager_operations_v63_v67.py'
new_template = root / 'floorplans/templates/floorplans/manager_operations_v63_v67.html'
if not py.is_file() or not html.is_file():
    sys.exit('Staff Hub files missing; no changes made.')
src, tmpl = py.read_text(), html.read_text()
if (new_module.exists() or new_template.exists()
        or 'V63_V67_MANAGER_OPERATIONS' in src or 'V63_V67_MANAGER_OPERATIONS' in tmpl):
    sys.exit('v63-v67 already installed or partially installed; no changes made.')
if ('operations_v58_v62' not in src or 'forecast_dates_v45' not in src
        or tmpl.count('<!-- V58_V62_OPERATIONS_START -->') != 1):
    sys.exit('v58-v62 prerequisites missing; no changes made.')
marker = '<!-- V58_V62_OPERATIONS_START -->'
pos = tmpl.index(marker)
stack = []
for match in re.finditer(r'{%\s*(if|elif|else|endif|for|empty|endfor|with|endwith)\b(.*?)%}', tmpl[:pos], re.S):
    tag, arg = match.group(1), match.group(2).strip()
    if tag in ('if', 'for', 'with'):
        stack.append((tag, arg))
    elif tag in ('endif', 'endfor', 'endwith'):
        expected = {'endif':'if', 'endfor':'for', 'endwith':'with'}[tag]
        if not stack or stack[-1][0] != expected:
            sys.exit('Template nesting could not be verified; no changes made.')
        stack.pop()
    elif tag == 'elif':
        if not stack or stack[-1][0] != 'if':
            sys.exit('Template nesting could not be verified; no changes made.')
        stack[-1] = ('if', arg)
    elif tag == 'else' and stack and stack[-1][0] == 'if':
        stack[-1] = ('if', 'ELSE:' + stack[-1][1])
if ('if', 'manager') not in stack:
    sys.exit('Manager-only placement not verified; no changes made.')
tree = ast.parse(src)
view = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'staff_hub']
if len(view) != 1:
    sys.exit('staff_hub view not found uniquely; no changes made.')
lines = src.splitlines(keepends=True)
today_nodes = [n for n in ast.walk(view[0]) if isinstance(n, ast.Assign)
    and any(isinstance(t,ast.Name) and t.id == 'today' for t in n.targets)
    and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute)
    and n.value.func.attr == 'localdate']
if len(today_nodes) != 1:
    sys.exit('Expected today assignment missing; no changes made.')
today_node = today_nodes[0]
if re.match(r'^\s*', lines[today_node.lineno-1]).group() != '    ':
    sys.exit('Unexpected staff_hub indentation; no changes made.')
addition = """    # V63_V67_MANAGER_OPERATIONS: read-only, hut-scoped dedicated page.
    if manager and request.GET.get('operations') == '1':
        selected_start = select_forecast_start(request.GET.get('forecast_start'), today)
        operations = build_manager_operations(hut, selected_start)
        return render(request, 'floorplans/manager_operations_v63_v67.html', {
            'hut': hut, 'today': today, 'forecast_start': selected_start,
            'forecast_max': today + timedelta(days=365), 'ops': operations,
        })
"""
lines.insert(today_node.end_lineno, addition)
first = tree.body[0]
insert_at = first.end_lineno if (isinstance(first,ast.Expr) and isinstance(first.value,ast.Constant)
    and isinstance(first.value.value,str)) else 0
lines.insert(insert_at, 'from .manager_operations_v63_v67 import build_manager_operations\n')
newsrc = ''.join(lines)
ast.parse(newsrc)
link = '''<!-- V63_V67_MANAGER_OPERATIONS -->
<section class="section card"><h2>Manager Operations · v63–v67</h2>
<p class="muted">Conflicts, room availability, arrival readiness and prioritized actions.</p>
<a class="link" href="?operations=1&amp;forecast_start={{ forecast_start_v45|date:'Y-m-d' }}">Open Manager Operations<span>Dedicated seven-day operational workspace</span></a></section>
'''
newtmpl = tmpl.replace(marker, link + '\n' + marker, 1)
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups, created = [], []
try:
    for p in (py, html):
        b = p.with_name(p.name + '.bak_v63_v67_' + stamp)
        shutil.copy2(p,b)
        backups.append((p,b))
    for source, dest in ((pkg/'manager_operations_v63_v67.py',new_module),
                         (pkg/'manager_operations_v63_v67.html',new_template)):
        shutil.copy2(source,dest)
        created.append(dest)
    py.write_text(newsrc)
    html.write_text(newtmpl)
except Exception:
    for p,b in backups: shutil.copy2(b,p)
    for p in created: p.unlink(missing_ok=True)
    raise
print('SummitDesk v63-v67 installed. Backups:')
for _,b in backups: print(' ',b)
print('Run Django checks and manager/cleaner access tests before restart.')
