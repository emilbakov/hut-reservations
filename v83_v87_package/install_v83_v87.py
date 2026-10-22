#!/usr/bin/env python3
"""Backup-first, fail-closed installer for the manager operations reporting package."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import shutil, sys

root = Path(__file__).resolve().parent.parent
pkg = Path(__file__).resolve().parent
hub = root/'floorplans/staff_hub.py'
page = root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
module = root/'floorplans/daily_reports_v83_v87.py'
required = [hub,page,root/'floorplans/daily_workspace_v78_v82.py',
            root/'floorplans/operations_filters_v73_v77.py']
if not all(p.is_file() for p in required):
    sys.exit('v78-v82 prerequisites missing. No changes made.')
source, html = hub.read_text(),page.read_text()
if module.exists() or 'DAILY_REPORTS_V83_V87' in html or 'DAILY_REPORTS_V83_V87' in source:
    sys.exit('Already installed or partially installed. No changes made.')
needle = '        daily = build_daily_workspace(hut, selected_start, operations)'
context = "'forecast_max': today + timedelta(days=365), 'ops': operations, 'daily': daily,"
if (source.count(needle)!=1 or source.count(context)!=1 or
    html.count('<!-- DAILY_WORKSPACE_END -->')!=1 or html.count('</head>')!=1):
    sys.exit('Expected manager-only daily workspace integration not found. No changes made.')
addition = """\n        # DAILY_REPORTS_V83_V87: manager-only; reuse computed hut-scoped data.
        issue_kind = request.GET.get('issue_kind', 'all')
        if issue_kind not in ISSUE_KINDS:
            issue_kind = 'all'
        visible_issues = filter_issues(daily['urgent'], issue_kind)
        readiness = arrival_readiness(daily['timeline'])
        daily_export = request.GET.get('daily_export', '')
        if daily_export == 'beds':
            return bed_details_csv(hut, daily)
        if daily_export == 'checklist':
            return checklist_csv(hut, daily)"""
new_source = source.replace(needle,needle+addition,1)
new_source = new_source.replace(context,context+"\n            'issue_kind': issue_kind, 'visible_issues': visible_issues, 'readiness': readiness,",1)
lines = new_source.splitlines(keepends=True)
tree = ast.parse(new_source)
insert_at=0
for node in tree.body:
    if (isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)) or (isinstance(node,ast.ImportFrom) and node.module=='__future__'):
        insert_at=node.end_lineno
    else:break
lines.insert(insert_at,'from .daily_reports_v83_v87 import ISSUE_KINDS, filter_issues, arrival_readiness, bed_details_csv, checklist_csv\n')
new_source=''.join(lines)
ast.parse(new_source)
new_html=html.replace('<!-- DAILY_WORKSPACE_END -->','<!-- DAILY_WORKSPACE_END -->\\n'+(pkg/'daily_reports_fragment.html').read_text(),1)
# The print layout only changes presentation; manager authorization remains in the view.
css="""<style media="print">
@page { size: A4; margin: 12mm; }
body { background:white!important;color:black!important;font-size:10pt; }
.hero {background:white!important;color:black!important;padding:0!important;}
.hero a, nav, form, button, #report-exports, #issue-filters, #print-operations,
.quick-links, a[href*="operations_export"], a[href*="daily_export"] {display:none!important;}
main {max-width:none!important;padding:0!important;}
.panel {border:0!important;break-inside:avoid;box-shadow:none!important;padding:8px 0!important;margin:4px 0!important;}
.scroll {overflow:visible!important;} table {min-width:0!important;font-size:8pt;}
th,td {padding:4px!important;} h2 {break-after:avoid;}
</style>"""
new_html=new_html.replace('</head>',css+'\\n</head>',1)
if new_html.count('DAILY_REPORTS_V83_V87')!=1:
    sys.exit('Unexpected report template marker. No changes made.')
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups=[];created=[]
try:
    for f in (hub,page):
        backup=f.with_name(f.name+'.bak_v83_v87_'+stamp)
        shutil.copy2(f,backup);backups.append((f,backup))
    shutil.copy2(pkg/'daily_reports_v83_v87.py',module);created.append(module)
    hub.write_text(new_source)
    page.write_text(new_html)
except Exception:
    for f,b in backups:shutil.copy2(b,f)
    for f in created:f.unlink(missing_ok=True)
    raise
print('Installed SummitDesk daily reports package. Backups:')
for _,b in backups:print(' ',b)
print('Run Django checks and manager/cleaner/cross-hut permission tests before restart.')
