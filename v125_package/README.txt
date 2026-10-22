SummitDesk v125 — Public hut detail and guest booking page
==========================================================
Prerequisite: v124 installed (public homepage and hut directory).

This release changes ONLY the public hut detail page /huts/<slug>/.
The booking service, room availability calculations, staff pages, and
legacy /book/ page remain unchanged.

Files installed:
- bookings/views.py (three minimal, guarded text replacements)
- bookings/templates/bookings/public_hut_v125.html (new)
- bookings/static/bookings/public_hut_v125.css (new)
- bookings/static/bookings/public_hut_v125.js (new)
- bookings/test_public_hut_v125.py (new)

Install from Django project root:
  unzip -o summitdesk_v125.zip
  python3 v125_package/install_v125.py

Activate your virtualenv, PostgreSQL environment, and settings as usual.
Then run:
  python manage.py check
  python manage.py test bookings.test_public_hut_v125
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service

Test an active hut via /huts/<slug>/ without dates and with valid dates.
Verify room prices, bed counts, guest fields, and submit a test booking.

Rollback (exact path printed by installer):
  python3 v125_package/rollback_v125.py summitdesk_backups/public_hut_TIMESTAMP
  python manage.py check
  sudo systemctl restart gunicorn.service

No database migrations. No changes to staff permissions.
The example design preview uses fictional hut details; live site uses DB data.
