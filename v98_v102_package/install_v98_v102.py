#!/usr/bin/env python3
"""Safe, template-only SummitDesk UI upgrade. Requires v93-v97."""
from pathlib import Path
from datetime import datetime, timezone
import shutil,sys
root=Path(__file__).resolve().parent.parent
pkg=Path(__file__).resolve().parent
page=root/'floorplans/templates/floorplans/manager_operations_v63_v67.html'
if not page.is_file():sys.exit('Manager Operations template missing; no changes made.')
src=page.read_text()
if ('OPERATIONS_SUMMARY_V93_V97' not in src or 'DAILY_TOOLS_V88_V92' not in src
    or src.count('</head>')!=1 or src.count('</body>')!=1 or '<main' not in src):
    sys.exit('Expected v93-v97 page not found; no changes made.')
if 'SUMMITDESK_UI_V98_V102' in src:sys.exit('UI package already installed; no changes made.')
css=(pkg/'ui.css').read_text()
js=(pkg/'ui.js').read_text()
if '</style>' in css or '</script>' in js:sys.exit('Unexpected asset content; no changes made.')
updated=src.replace('</head>','<style id="SUMMITDESK_UI_V98_V102">\n'+css+'\n</style></head>',1)
updated=updated.replace('</body>','<script>\n'+js+'\n</script></body>',1)
# Don't touch views, URLs, database, template logic or other files.
stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backup=page.with_name(page.name+'.bak_v98_v102_'+stamp)
shutil.copy2(page,backup)
try:page.write_text(updated)
except Exception:
    shutil.copy2(backup,page)
    raise
print('Installed UI upgrade. Original template backup:',backup)
print('Run Django check, then verify desktop/mobile and all five navigation sections.')
