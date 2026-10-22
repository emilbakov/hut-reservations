#!/usr/bin/env python3
"""Backup-first installer for the five daily-operations improvements."""
import ast
from datetime import datetime,timezone
from pathlib import Path
import re,shutil,sys
root=Path(__file__).resolve().parent.parent
pkg=Path(__file__).resolve().parent
hub=root/'floorplans/staff_hub.py'
page=root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
module=root/'floorplans/daily_workspace_v78_v82.py'
if not all(p.is_file() for p in (hub,page,root/'floorplans/operations_filters_v73_v77.py',root/'floorplans/manager_operations_v63_v67.py')):
    sys.exit('Prerequisite v73-v77 files not found. No changes made.')
source=hub.read_text();html=page.read_text()
if module.exists() or 'DAILY_WORKSPACE_START' in html or 'DAILY_WORKSPACE_V78_V82' in source:
    sys.exit('Already installed or partially installed. No changes made.')
needle="        operations = build_manager_operations(hut, selected_start)"
if source.count(needle)!=1 or html.count('</main>')!=1 or 'V73_V77_ACTION_TOOLS' not in html:
    sys.exit('Expected manager integration not found uniquely. No changes made.')
new_source=source.replace(needle,needle+"\n        # DAILY_WORKSPACE_V78_V82: manager-only, hut-scoped, read-only.\n        daily = build_daily_workspace(hut, selected_start, operations)",1)
ctx="'forecast_max': today + timedelta(days=365), 'ops': operations,"
if new_source.count(ctx)!=1:
    sys.exit('Expected manager context not found uniquely. No changes made.')
new_source=new_source.replace(ctx,ctx+" 'daily': daily,",1)
tree=ast.parse(new_source)
lines=new_source.splitlines(keepends=True)
insert_at=0
for node in tree.body:
    if (isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)) or (isinstance(node,ast.ImportFrom) and node.module=='__future__'):
        insert_at=node.end_lineno
    else:break
lines.insert(insert_at,'from .daily_workspace_v78_v82 import build_daily_workspace\n')
new_source=''.join(lines)
ast.parse(new_source)
fragment=(pkg/'daily_workspace_fragment.html').read_text()
new_html=html.replace('</main>',fragment+'\n</main>',1)
# Earlier action tools were appended after </html> by the previous installer.
# Move that block into the page, retaining its marker and form controls.
legacy_marker='<!-- V73_V77_ACTION_TOOLS -->'
if new_html.count(legacy_marker)==1 and new_html.index(legacy_marker)>new_html.index('</html>'):
    start=new_html.index(legacy_marker)
    action_tools=new_html[start:]
    new_html=new_html[:start]
    new_html=new_html.replace('</main>',action_tools+'\n</main>',1)
# Strip technical version labels only in text, never HTML tags or comments.
parts=re.split(r'(<!--.*?-->|<[^>]+>)',new_html,flags=re.S)
for i,part in enumerate(parts):
    if part.startswith('<'):
        continue
    parts[i]=re.sub(r'(?i)\bv\d+(?:[–-]v?\d+)?\s*[·:]?\s*','',part)
new_html=''.join(parts)
# Remove technical version labels from existing staff-hub manager entry only.
hub_template=root/'floorplans/templates/floorplans/staff_hub.html'
hub_html=hub_template.read_text() if hub_template.is_file() else None
new_hub_html=hub_html.replace('Manager Operations · v63–v67','Manager Operations') if hub_html is not None else None
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups=[];created=[]
try:
    files=[hub,page]+([hub_template] if hub_html is not None and new_hub_html!=hub_html else [])
    for f in files:
        b=f.with_name(f.name+'.bak_v78_v82_'+stamp)
        shutil.copy2(f,b);backups.append((f,b))
    shutil.copy2(pkg/'daily_workspace.py',module);created.append(module)
    hub.write_text(new_source)
    page.write_text(new_html)
    if hub_html is not None and new_hub_html!=hub_html:
        hub_template.write_text(new_hub_html)
except Exception:
    for f,b in backups:shutil.copy2(b,f)
    for f in created:f.unlink(missing_ok=True)
    raise
print('Daily Operations package installed. Backups:')
for _,b in backups:print(' ',b)
print('Run Django checks and permission tests before restart.')
