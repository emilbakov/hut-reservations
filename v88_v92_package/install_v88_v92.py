#!/usr/bin/env python3
# Backup-first, fail-closed, idempotent v88-v92 installer.
import ast
from datetime import datetime, timezone
from pathlib import Path
import shutil, sys
root=Path(__file__).resolve().parent.parent
pkg=Path(__file__).resolve().parent
hub=root/'floorplans/staff_hub.py'
page=root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
module=root/'floorplans/daily_tools_v88_v92.py'
if not all(p.is_file() for p in (hub,page,root/'floorplans/daily_reports_v83_v87.py',root/'floorplans/daily_workspace_v78_v82.py')):
    sys.exit('v83-v87 prerequisites missing. No changes made.')
source,html=hub.read_text(),page.read_text()
if module.exists() or 'DAILY_TOOLS_V88_V92' in source or 'DAILY_TOOLS_V88_V92' in html:
    sys.exit('Already installed or partially installed. No changes made.')
needle="        visible_issues = filter_issues(daily['urgent'], issue_kind)"
needle2="        readiness = arrival_readiness(daily['timeline'])"
ctx="'issue_kind': issue_kind, 'visible_issues': visible_issues, 'readiness': readiness,"
checks=(source.count(needle)==1,source.count(needle2)==1,source.count(ctx)==1,
        html.count('<!-- DAILY_REPORTS_V83_V87 -->')==1,
        html.count('id="issue-filters"')==1,html.count('id="readiness-summary"')==1,
        html.count('</main>')==1,html.count('name="issue_kind"')==1)
if not all(checks):
    sys.exit('Expected manager-only reporting integration not found uniquely. No changes made.')
source=source.replace(needle,needle+"\n        issue_q = request.GET.get('issue_q', '').strip()[:100]\n        visible_issues = search_issues(visible_issues, issue_q)",1)
source=source.replace(needle2,needle2+"\n        readiness_mode = request.GET.get('readiness_mode', 'all')\n        if readiness_mode not in ('all', 'review'):\n            readiness_mode = 'all'\n        readiness = select_readiness(readiness, readiness_mode)\n        daily_tools_export = request.GET.get('daily_tools_export', '')\n        if daily_tools_export == 'issues':\n            return issues_csv(hut, visible_issues)\n        if daily_tools_export == 'readiness':\n            return readiness_csv(hut, readiness)",1)
source=source.replace(ctx,ctx+"\n            'issue_q': issue_q, 'readiness_mode': readiness_mode,",1)
tree=ast.parse(source); lines=source.splitlines(keepends=True); insert_at=0
for n in tree.body:
    if (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)) or (isinstance(n,ast.ImportFrom) and n.module=='__future__'):
        insert_at=n.end_lineno
    else:break
lines.insert(insert_at,'from .daily_tools_v88_v92 import search_issues, select_readiness, issues_csv, readiness_csv\n')
source=''.join(lines);ast.parse(source)
# Preserve the existing issue-type selector, add search and a matching export link.
needle_html='<button type="submit">Filter issues</button></form>'
if html.count(needle_html)!=1:sys.exit('Issue filter form changed; no changes made.')
html=html.replace(needle_html,'''<label for="issue_q">Search issues</label>
<input id="issue_q" name="issue_q" maxlength="100" value="{{ issue_q }}" placeholder="Room or issue">
<button type="submit">Filter issues</button></form>
<p><a href="?operations=1&amp;forecast_start={{ forecast_start|date:'Y-m-d' }}&amp;issue_kind={{ issue_kind|urlencode }}&amp;issue_q={{ issue_q|urlencode }}&amp;daily_tools_export=issues">Export matching issues CSV</a></p>''',1)
needle_html='<section class="panel" id="readiness-summary"><h2>Arrival readiness summary</h2>'
if html.count(needle_html)!=1:sys.exit('Readiness section changed; no changes made.')
html=html.replace(needle_html,needle_html+'''
<form method="get" aria-label="Filter arrival readiness">
<input type="hidden" name="operations" value="1">
<input type="hidden" name="forecast_start" value="{{ forecast_start|date:'Y-m-d' }}">
<label for="readiness_mode">Show days</label><select id="readiness_mode" name="readiness_mode">
<option value="all" {% if readiness_mode == 'all' %}selected{% endif %}>All days</option>
<option value="review" {% if readiness_mode == 'review' %}selected{% endif %}>Days needing review</option>
</select><button type="submit">Apply</button></form>
<p>Showing {{ readiness|length }} days. <a href="?operations=1&amp;forecast_start={{ forecast_start|date:'Y-m-d' }}&amp;readiness_mode={{ readiness_mode|urlencode }}&amp;daily_tools_export=readiness">Export matching readiness CSV</a></p>''',1)
html=html.replace('<!-- DAILY_REPORTS_V83_V87 -->',(pkg/'quick_navigation.html').read_text()+'\\n<!-- DAILY_REPORTS_V83_V87 -->'.replace('\\n','\\n'),1)
if html.count('DAILY_TOOLS_V88_V92')!=1:sys.exit('Navigation insertion failed; no changes made.')
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'); backups=[]; created=[]
try:
    for p in (hub,page):
        b=p.with_name(p.name+'.bak_v88_v92_'+stamp);shutil.copy2(p,b);backups.append((p,b))
    shutil.copy2(pkg/'daily_tools_v88_v92.py',module);created.append(module)
    hub.write_text(source);page.write_text(html)
except Exception:
    for p,b in backups:shutil.copy2(b,p)
    for p in created:p.unlink(missing_ok=True)
    raise
print('Installed SummitDesk v88-v92. Backups:')
for _,b in backups:print(' ',b)
print('Run Django checks and manager/cleaner/cross-hut permission tests before restart.')
