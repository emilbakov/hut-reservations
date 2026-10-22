#!/usr/bin/env python3
"""Backup-first, fail-closed template-only calendar UI update."""
from pathlib import Path
from datetime import datetime, timezone
import shutil, sys
root=Path(__file__).resolve().parent.parent
pkg=Path(__file__).resolve().parent
page=root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
if not page.is_file():sys.exit('Manager Operations page missing; no changes made.')
src=page.read_text()
requirements=('SUMMITDESK_UI_V98_V102','Room availability calendar','bed-details','DAILY_TOOLS_V88_V92')
if any(req not in src for req in requirements) or src.count('</head>')!=1 or src.count('</body>')!=1:
    sys.exit('Expected v98-v102 template missing; no changes made.')
if 'SUMMITDESK_CALENDAR_V103_V107' in src:
    sys.exit('Calendar UI already installed; no changes made.')
css=(pkg/'calendar.css').read_text();js=(pkg/'calendar.js').read_text()
if '</style>' in css or '</script>' in js:
    sys.exit('Invalid embedded asset content; no changes made.')
new=src.replace('</head>','<style id="SUMMITDESK_CALENDAR_V103_V107">\n'+css+'\n</style></head>',1)
new=new.replace('</body>','<script>\n'+js+'\n</script></body>',1)
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backup=page.with_name(page.name+'.bak_v103_v107_'+stamp)
shutil.copy2(page,backup)
try:page.write_text(new)
except Exception:
    shutil.copy2(backup,page)
    raise
print('Installed calendar UI improvements. Backup:',backup)
print('No view, database or URL changes. Run Django check and test the calendar.')
