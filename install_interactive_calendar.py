"""Install additive staff calendar actions; idempotent and backed up."""
from pathlib import Path
from shutil import copy2
urls = Path('bookings/urls.py')
template = Path('bookings/templates/bookings/availability_calendar.html')
for f in (urls, template, Path('bookings/availability_calendar.py'), Path('bookings/services.py')):
    if not f.is_file():
        raise SystemExit(f'Missing {f}; run from Django project root after Availability Calendar.')
if "name='availability_calendar'" not in urls.read_text():
    raise SystemExit('Availability calendar URL missing; no changes made.')
for f in (urls, template):
    backup = f.with_name(f.name + '.before_interactive_calendar')
    if not backup.exists(): copy2(f, backup)
if "name='calendar_create'" not in urls.read_text():
    urls.write_text(urls.read_text().rstrip() + '''

from .calendar_actions import calendar_create, calendar_edit
urlpatterns += [
    path('staff/availability/new/', calendar_create, name='calendar_create'),
    path('staff/availability/edit/<str:code>/', calendar_edit, name='calendar_edit'),
]
''')
text = template.read_text()
if 'bookings:calendar_create' not in text:
    text = text.replace('<div class="av-scroll"', '''<p><a href="{% url 'bookings:calendar_create' %}{% if selected_slug %}?hut={{ selected_slug|urlencode }}{% endif %}">+ Create reservation</a></p>
<div class="av-scroll"''', 1)
    text = text.replace('<span class="av-number">{{ cell.available }}</span>', '''<a href="{% url 'bookings:calendar_create' %}?check_in={{ cell.day|date:'Y-m-d' }}&amp;room={{ row.room.pk }}{% if selected_slug %}&amp;hut={{ selected_slug|urlencode }}{% endif %}" title="Create booking for this date">+ Book</a><br>
<span class="av-number">{{ cell.available }}</span>''')
    text = text.replace('{{ r.code }} · {{ r.guest }}', '''<a href="{% url 'bookings:calendar_edit' r.code %}{% if selected_slug %}?hut={{ selected_slug|urlencode }}{% endif %}">{{ r.code }}</a> · {{ r.guest }}''')
    template.write_text(text)
print('Installed interactive calendar. No migration needed.')
