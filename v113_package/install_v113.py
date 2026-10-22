#!/usr/bin/env python3
"""Backup-first, safe installation of the actual reservation timeline redesign."""
import ast
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parent.parent
pkg = Path(__file__).resolve().parent
view = root / 'bookings/calendar_timeline.py'
page = root / 'bookings/templates/bookings/calendar_timeline.html'
helper = root / 'bookings/timeline_helpers_v113.py'
if not view.is_file() or not page.is_file():
    sys.exit('Original weekly timeline not found. No changes made.')
src = view.read_text()
old = page.read_text()
if helper.exists() or 'V113_TIMELINE_LAYOUT' in src:
    sys.exit('Already installed or partial installation found. No changes made.')
needle = "        rows.append({'room': room, 'cells': cells})"
context_needle = "        'rows': rows, 'days': days, 'start': start,"
if src.count(needle) != 1 or src.count(context_needle) != 1 or 'calendar_move' not in old:
    sys.exit('Timeline integration does not match expected source. No changes made.')
src = src.replace(needle, """        # V113_TIMELINE_LAYOUT: booking bars span the nights occupied.
        room_items = [item for item in items if item.room_id == room.pk]
        bars = build_bars(room_items, start, end)
        track_count = max((bar['track'] for bar in bars), default=1)
        rows.append({'room': room, 'cells': cells, 'bars': bars,
                     'track_count': track_count, 'grid_end': track_count + 1})""", 1)
src = src.replace(context_needle, "        'rows': rows, 'days': days, 'start': start, 'today': timezone.localdate(),\n        'last_day': days[-1], 'booking_count': sum(len(row['bars']) for row in rows),", 1)
src = 'from .timeline_helpers_v113 import build_bars\n' + src
ast.parse(src)
newpage = (pkg / 'calendar_timeline.html').read_text()
if '{% url "bookings:calendar_move" %}' not in newpage:
    sys.exit('Move confirmation link missing from replacement. No changes made.')
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backups = []
try:
    for path in (view, page):
        backup = path.with_name(path.name + '.bak_v113_' + stamp)
        shutil.copy2(path, backup)
        backups.append((path, backup))
    shutil.copy2(pkg / 'timeline_helpers.py', helper)
    view.write_text(src)
    page.write_text(newpage)
except Exception:
    for path, backup in backups:
        shutil.copy2(backup, path)
    helper.unlink(missing_ok=True)
    raise
print('Installed SummitDesk v113 reservation timeline redesign.')
for _, backup in backups:
    print('Backup:', backup)
print('Run Django checks and test reservation links, hut permissions, and move confirmation before restarting.')
