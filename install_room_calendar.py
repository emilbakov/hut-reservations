"""Idempotently register the manager room calendar URL; backup first."""
from pathlib import Path

path = Path('bookings/urls.py')
text = path.read_text()
if 'name="room_calendar"' in text or "name='room_calendar'" in text:
    print('Room calendar URL already installed.')
else:
    if 'urlpatterns' not in text or 'from django.urls import path' not in text:
        raise SystemExit('Unexpected urls.py layout; no changes made.')
    backup = path.with_name('urls.py.before_room_calendar')
    if not backup.exists():
        backup.write_text(text)
    text += '''\n# Manager room availability calendar\nfrom . import room_calendar\nurlpatterns += [\n    path("staff/rooms/calendar/", room_calendar.room_calendar, name="room_calendar"),\n]\n'''
    path.write_text(text)
    print('Installed /staff/rooms/calendar/; backup:', backup)
