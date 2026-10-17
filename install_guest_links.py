"""Idempotent installer for guest portal links in confirmation and manager controls."""
from pathlib import Path
from shutil import copy2

views = Path('bookings/views.py')
urls = Path('bookings/urls.py')
dashboard = Path('bookings/templates/bookings/manager_reservations.html')
models = Path('bookings/models.py')
for path in (views, urls, dashboard, models):
    if not path.is_file():
        raise SystemExit(f'Missing {path}. Run from project root.')
if 'class GuestAccessLink(models.Model):' not in models.read_text():
    raise SystemExit('Install Guest Self-Service first.')

# Validate compatibility BEFORE modifying any project file.
source = views.read_text()
start = source.find('def send_confirmation(request, reservation):')
end = source.find('\n@', start + 1) if start >= 0 else -1
if end < 0:
    end = len(source)
section = source[start:end] if start >= 0 else ''
needle = '    for recipient in recipients:\n'
if 'append_guest_portal_to_confirmation' not in section and needle not in section:
    raise SystemExit('Cannot safely locate send_confirmation recipient loop. No files changed.')
if 'name=\'guest_link_controls\'' not in urls.read_text() and 'urlpatterns' not in urls.read_text():
    raise SystemExit('Cannot locate urlpatterns. No files changed.')

for path in (views, urls, dashboard):
    backup = path.with_name(path.name + '.before_guest_links')
    if not backup.exists():
        copy2(path, backup)

if 'append_guest_portal_to_confirmation' not in section:
    # Guest gets the private URL; keeper/admin copies keep their existing body.
    replacement = '''    from .guest_links import append_guest_portal_to_confirmation
    guest_body = append_guest_portal_to_confirmation(request, reservation, body)
    for recipient in recipients:
'''
    section = section.replace(needle, replacement, 1)
    # Keep any custom subject/body logic from the guest communications module.
    # Restrict substitution to the confirmation function's send_mail call.
    import re
    pattern = r'(send_mail\([^\n]*?,\s*)body(\s*,\s*None\s*,\s*\[recipient\])'
    section, count = re.subn(pattern, r'\1(guest_body if recipient == reservation.email else body)\2', section, count=1)
    if count != 1:
        raise SystemExit('Unexpected confirmation send_mail call; backups created, no files modified.')
    views.write_text(source[:start] + section + source[end:])

if "name='guest_link_controls'" not in urls.read_text():
    urls.write_text(urls.read_text().rstrip() + '''

from .guest_links import guest_link_controls
urlpatterns += [
    path('staff/guest-links/', guest_link_controls, name='guest_link_controls'),
]
''')
if 'bookings:guest_link_controls' not in dashboard.read_text():
    content = dashboard.read_text()
    content = content.replace('{% block content %}', '''{% block content %}
<p><a href="{% url 'bookings:guest_link_controls' %}">Guest access links</a></p>''', 1)
    dashboard.write_text(content)
print('Installed guest links. No migration required. Run tests before restart.')
