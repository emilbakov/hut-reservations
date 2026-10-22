#!/usr/bin/env python3
"""Fail-closed backup-first installer; requires v68-v72."""
import ast
from datetime import datetime,timezone
from pathlib import Path
import shutil,sys
root=Path(__file__).resolve().parent.parent
pkg=Path(__file__).resolve().parent
hub=root/'floorplans/staff_hub.py'
tmpl=root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
mod=root/'floorplans/operations_filters_v73_v77.py'
if not hub.is_file() or not tmpl.is_file() or not (root/'floorplans/operations_exports_v68_v72.py').is_file():
    sys.exit('v68-v72 prerequisites missing; no changes made.')
source,html=hub.read_text(),tmpl.read_text()
if mod.exists() or 'V73_V77_ACTION_TOOLS' in source or 'V73_V77_ACTION_TOOLS' in html:
    sys.exit('v73-v77 already installed or partially installed; no changes made.')
needle="        displayed_actions = filter_actions(operations['actions'], action_level)\n"
if source.count(needle)!=1 or html.count('<!-- V68_V72_EXPORTS -->')!=1:
    sys.exit('Expected v68-v72 integration not found uniquely; no changes made.')
replace="""        # V73_V77_ACTION_TOOLS: filters and CSV share the same result set.
        action_q = request.GET.get('action_q', '').strip()[:100]
        action_day = request.GET.get('action_day', '')
        valid_days = {d.isoformat() for d in operations['dates']}
        if action_day not in valid_days:
            action_day = ''
        action_sort = request.GET.get('action_sort', 'priority')
        if action_sort not in SORTS:
            action_sort = 'priority'
        displayed_actions = select_actions(
            filter_actions(operations['actions'], action_level),
            query=action_q, action_date=action_day, sort=action_sort,
        )
        action_summary = summarize_actions(displayed_actions)
"""
new_source=source.replace(needle,replace,1)
ctx="'displayed_actions': displayed_actions, 'action_level': action_level,"
if new_source.count(ctx)!=1:
    sys.exit('Expected operations context missing; no changes made.')
new_source=new_source.replace(ctx,ctx+"\n            'action_q': action_q, 'action_day': action_day, 'action_sort': action_sort,\n            'action_summary': action_summary,",1)
# Insert import after module docstring/future imports without breaking syntax.
tree=ast.parse(new_source)
insert_at=0
for node in tree.body:
    if (isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)) or (isinstance(node,ast.ImportFrom) and node.module=='__future__'):
        insert_at=node.end_lineno
    else:break
lines=new_source.splitlines(keepends=True)
lines.insert(insert_at,'from .operations_filters_v73_v77 import SORTS, select_actions, summarize_actions\n'.replace('\\n','\n'))
new_source=''.join(lines)
ast.parse(new_source)
anchor='<h2>v66 · Manager action center</h2>'
if html.count(anchor)!=1 or html.count('{% for a in displayed_actions %}')!=1:
    sys.exit('Unexpected action center template; no changes made.')
fragment=(pkg/'filters_fragment.html').read_text()
new_html=html.replace(anchor,anchor+'\n'+fragment,1)
# Remove old v72 form to avoid duplicate action_level fields and competing forms.
old_start='<form method="get" aria-label="Filter manager actions">'
old_end='</select><button type="submit">Apply</button></form>'
if new_html.count(old_start)!=1 or new_html.count(old_end)!=1:
    sys.exit('Expected old filter form not found uniquely; no changes made.')
a=new_html.index(old_start);b=new_html.index(old_end,a)+len(old_end)
new_html=new_html[:a]+new_html[b:]
# Old v71 export link stays available but v76 provides a fully-filtered URL.
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups=[]
try:
    for f in (hub,tmpl):
        backup=f.with_name(f.name+'.bak_v73_v77_'+stamp)
        shutil.copy2(f,backup);backups.append((f,backup))
    shutil.copy2(pkg/'operations_filters_v73_v77.py',mod)
    hub.write_text(new_source)
    tmpl.write_text(new_html)
except Exception:
    for f,b in backups:shutil.copy2(b,f)
    mod.unlink(missing_ok=True)
    raise
print('Installed v73-v77; backups:')
for _,b in backups:print(' ',b)
print('Run Django check and manager/cleaner/cross-hut permission tests.')
