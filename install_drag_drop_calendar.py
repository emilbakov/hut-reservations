"""Idempotent additive installation for weekly drag/drop calendar."""
from pathlib import Path
from shutil import copy2
urls = Path('bookings/urls.py')
monthly = Path('bookings/templates/bookings/availability_calendar.html')
for file in (urls, monthly, Path('bookings/calendar_actions.py'), Path('bookings/services.py')):
    if not file.is_file(): raise SystemExit(f'Missing {file}. Install Interactive Calendar first.')
if "name='calendar_edit'" not in urls.read_text():
    raise SystemExit('Calendar edit route missing. Install Interactive Calendar first.')
for file in (urls, monthly):
    backup = file.with_name(file.name + '.before_drag_drop_calendar')
    if not backup.exists(): copy2(file, backup)
if "name='calendar_timeline'" not in urls.read_text():
    urls.write_text(urls.read_text().rstrip()+'''\n\nfrom .calendar_timeline import calendar_timeline
from .calendar_drag import calendar_move
urlpatterns += [
    path('staff/availability/week/', calendar_timeline, name='calendar_timeline'),
    path('staff/availability/move/', calendar_move, name='calendar_move'),
]
''')
if "bookings:calendar_timeline" not in monthly.read_text():
    monthly.write_text(monthly.read_text().replace('{% block content %}', '''{% block content %}
<p><a href="{% url 'bookings:calendar_timeline' %}{% if selected_slug %}?hut={{ selected_slug|urlencode }}{% endif %}">Open weekly drag-and-drop timeline →</a></p>''',1))
print('Weekly drag-and-drop calendar installed. No migrations required.')
