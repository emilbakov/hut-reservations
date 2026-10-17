"""Install the read-only availability calendar; idempotent, no model migrations."""
from pathlib import Path
from shutil import copy2

urls = Path('bookings/urls.py')
dashboard = Path('bookings/templates/bookings/manager_reservations.html')
views = Path('bookings/views.py')
models = Path('bookings/models.py')
for file in (urls, dashboard, views, models):
    if not file.is_file():
        raise SystemExit(f'Missing {file}. Run from the Django project root.')
if 'def permitted_hut_selection(request):' not in views.read_text():
    raise SystemExit('Required multi-hut permission helper not found. No files changed.')
if 'class ReservationItem(models.Model):' not in models.read_text():
    raise SystemExit('Expected reservation model not found. No files changed.')
if 'urlpatterns' not in urls.read_text():
    raise SystemExit('Cannot locate urlpatterns. No files changed.')
for file in (urls, dashboard):
    backup = file.with_name(file.name + '.before_availability_calendar')
    if not backup.exists():
        copy2(file, backup)
if "name='availability_calendar'" not in urls.read_text():
    urls.write_text(urls.read_text().rstrip() + '''

from .availability_calendar import availability_calendar
urlpatterns += [
    path('staff/availability/', availability_calendar, name='availability_calendar'),
]
''')
if "bookings:availability_calendar" not in dashboard.read_text():
    content = dashboard.read_text()
    if '{% block content %}' not in content:
        raise SystemExit('Cannot locate dashboard content block; URL installed but dashboard link not added.')
    dashboard.write_text(content.replace('{% block content %}', '''{% block content %}
<p><a href="{% url 'bookings:availability_calendar' %}">Availability calendar</a></p>''', 1))
print('Availability calendar installed. No migration required. Run tests before restarting.')
