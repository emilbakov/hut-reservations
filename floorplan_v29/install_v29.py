#!/usr/bin/env python3
"""V29 additive template navigation patch. Run from Django project root."""
from pathlib import Path
import re, shutil, sys
from datetime import datetime

ROOT=Path.cwd()
TEMPLATES=ROOT/'floorplans/templates/floorplans'
NAMES=['staff_arrivals.html','staff_overview.html','staff_new_booking.html','staff_reservation.html','staff_transfer.html','staff_calendar.html','staff_hub.html','staff_housekeeping.html','staff_tasks.html','cleaner_portal.html','cleaner_team.html','cleaner_invitations.html']
STAMP=datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP=ROOT/f'backups_v29_{STAMP}'
if not TEMPLATES.is_dir():
    sys.exit('ERROR: Run this script from /home/deploy/hut-reservations; floorplans templates missing.')
if not (ROOT/'floorplans/templatetags/summitdesk_nav.py').is_file():
    sys.exit('ERROR: V28 shared navigation is not installed. Install V28 first.')
changes=[]; skipped=[]
for name in NAMES:
    file=TEMPLATES/name
    if not file.is_file():
        skipped.append(name+' (not found)');continue
    source=file.read_text(encoding='utf-8')
    if '{% summitdesk_nav %}' in source:
        skipped.append(name+' (already integrated)');continue
    match=re.search(r'<body\b[^>]*>',source,re.I)
    if not match:
        skipped.append(name+' (no body tag; manual review)');continue
    patched=source[:match.end()]+'\n{% summitdesk_nav %}\n'+source[match.end():]
    # Django's load tag can be added at the beginning regardless of existing loads.
    patched='{% load summitdesk_nav %}\n'+patched
    BACKUP.mkdir(parents=True,exist_ok=True)
    shutil.copy2(file,BACKUP/name)
    file.write_text(patched,encoding='utf-8')
    changes.append(name)
print('Backups:',BACKUP if changes else 'none needed')
print('Updated:',', '.join(changes) or 'none')
print('Skipped:',', '.join(skipped) or 'none')
print('Run python manage.py check and visually test the pages before restarting.')
