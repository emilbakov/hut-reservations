#!/usr/bin/env python3
import ast,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parent.parent;pkg=Path(__file__).resolve().parent
hub=root/'floorplans/staff_hub.py';page=root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
target=root/'floorplans/operations_summary_v93_v97.py'
if not all(p.exists() for p in (hub,page,root/'floorplans/daily_tools_v88_v92.py')):sys.exit('Requires v88-v92; no changes made.')
src=hub.read_text();html=page.read_text()
if target.exists() or 'OPERATIONS_SUMMARY_V93_V97' in src or 'OPERATIONS_SUMMARY_V93_V97' in html:sys.exit('Already installed or partial install; no changes made.')
needles=["        visible_issues = search_issues(visible_issues, issue_q)","        readiness = select_readiness(readiness, readiness_mode)","        if daily_tools_export == 'issues':","'issue_q': issue_q, 'readiness_mode': readiness_mode,"]
if any(src.count(n)!=1 for n in needles) or html.count('<!-- DAILY_TOOLS_V88_V92 -->')!=1 or html.count('<button type="submit">Filter issues</button>')!=1 or html.count('<button type="submit">Apply</button></form>')!=1:sys.exit('Expected integration missing; no changes made.')
src=src.replace(needles[0],needles[0]+'''
        issue_order = request.GET.get('issue_order','earliest')
        if issue_order not in ('earliest','latest','title'): issue_order='earliest'
        visible_issues = sort_issues(visible_issues,issue_order)''',1)
src=src.replace(needles[1],needles[1]+'''
        readiness_order = request.GET.get('readiness_order','earliest')
        if readiness_order not in ('earliest','latest','most_work'): readiness_order='earliest'
        readiness = sort_readiness(readiness,readiness_order)
        attention = attention_totals(visible_issues,readiness)''',1)
src=src.replace(needles[2],'''        # OPERATIONS_SUMMARY_V93_V97
        if daily_tools_export == 'summary':
            return summary_csv(hut,visible_issues,readiness)
'''+needles[2],1)
src=src.replace(needles[3],needles[3]+"\n            'issue_order':issue_order,'readiness_order':readiness_order,'attention':attention,",1)
tree=ast.parse(src);lines=src.splitlines(keepends=True);at=0
for n in tree.body:
    if (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)) or (isinstance(n,ast.ImportFrom) and n.module=='__future__'):at=n.end_lineno
    else:break
lines.insert(at,'from .operations_summary_v93_v97 import sort_issues,sort_readiness,attention_totals,summary_csv\n')
src=''.join(lines);ast.parse(src)
html=html.replace('<button type="submit">Filter issues</button>','''<label for="issue_order">Sort issues</label><select id="issue_order" name="issue_order"><option value="earliest">Earliest first</option><option value="latest" {% if issue_order == 'latest' %}selected{% endif %}>Latest first</option><option value="title" {% if issue_order == 'title' %}selected{% endif %}>By title</option></select><button type="submit">Filter issues</button>''',1)
html=html.replace('<button type="submit">Apply</button></form>','''<label for="readiness_order">Sort readiness</label><select id="readiness_order" name="readiness_order"><option value="earliest">Earliest first</option><option value="latest" {% if readiness_order == 'latest' %}selected{% endif %}>Latest first</option><option value="most_work" {% if readiness_order == 'most_work' %}selected{% endif %}>Most work first</option></select><button type="submit">Apply</button></form>''',1)
fragment=(pkg/'summary_fragment.html').read_text()
html=html.replace('<!-- DAILY_TOOLS_V88_V92 -->',fragment+'\n<!-- DAILY_TOOLS_V88_V92 -->',1)
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f');backups=[];created=[]
try:
    for p in (hub,page):
        b=p.with_name(p.name+'.bak_v93_v97_'+stamp);shutil.copy2(p,b);backups.append((p,b))
    shutil.copy2(pkg/'operations_summary_v93_v97.py',target);created.append(target)
    hub.write_text(src);page.write_text(html)
except Exception:
    for p,b in backups:shutil.copy2(b,p)
    for p in created:p.unlink(missing_ok=True)
    raise
print('Installed v93-v97; backups:')
for _,b in backups:print(b)
