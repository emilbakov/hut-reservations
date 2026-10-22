#!/usr/bin/env python3
"""Backup-first, fail-closed template-only SummitDesk calendar usability update."""
from pathlib import Path
from datetime import datetime,timezone
import shutil,sys
root=Path(__file__).resolve().parent.parent
pkg=Path(__file__).resolve().parent
page=root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
if not page.is_file():sys.exit('Manager Operations template missing; no changes made.')
src=page.read_text()
if 'SUMMITDESK_CALENDAR_V103_V107' not in src or src.count('</head>')!=1 or src.count('</body>')!=1:
    sys.exit('Expected v103-v107 calendar missing; no changes made.')
if 'SUMMITDESK_CALENDAR_V108_V112' in src:
    sys.exit('Calendar controls already installed; no changes made.')
css=(pkg/'calendar_controls.css').read_text()
js=(pkg/'calendar_controls.js').read_text()
if '</style>' in css or '</script>' in js:
    sys.exit('Unexpected embedded closing tag; no changes made.')
updated=src.replace('</head>','<style id="SUMMITDESK_CALENDAR_V108_V112">\\n'+css+'\\n</style></head>',1)
updated=updated.replace('</body>','<script>\\n'+js+'\\n</script></body>',1)
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backup=page.with_name(page.name+'.bak_v108_v112_'+stamp)
shutil.copy2(page,backup)
try:page.write_text(updated)
except Exception:
    shutil.copy2(backup,page)
    raise
print('Installed calendar usability improvements. Backup:',backup)
print('No view, database or URL changes. Run Django check and test on mobile.')
