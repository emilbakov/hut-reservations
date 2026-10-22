SummitDesk v140 - Screenshot-inspired Property Calendar quick stay

Existing Property Calendar (one hut) gains a date-selectable monthly room grid and a booking sidebar.
Click an arrival day, then departure in the same room. Enter guest name; email/phone optional.
Guests count means BEDS requested, not a whole-room booking.
Server confirms the stay immediately via bookings.services.create_reservation with CONFIRMED status.
It enforces per-night capacity, maintenance closures, room active state, booking horizon, CSRF and staff/hut authorization.
The departure day is exclusive. A room's displayed price is per bed per night.
For stays crossing a month, use the date inputs in the sidebar; the server validates all nights.

Requires installed v138 Property Calendar, with or without v139 Today Focus.
The installer requires exact v138/v139 baseline templates and v138 helper; it will refuse unknown edits.
It changes: property_calendar_v138.html, property_calendar_v138.py, floorplans/urls.py.
It adds: property_quickstay_v140.py, test_quickstay_v140.py.
It does NOT modify bookings/services.py or the separate Reservation Calendar.
No database migrations. It makes a timestamped backup and prints the rollback command.

From /home/deploy/hut-reservations:
  unzip -o summitdesk_v140_quickstay.zip
  python3 v140_quickstay_package/install_v140_quickstay.py --check
  python3 v140_quickstay_package/install_v140_quickstay.py
  source myprojectenv/bin/activate
  python manage.py test floorplans.test_quickstay_v140 floorplans.test_property_calendar_v138 --settings=config.settings

If your settings enforce SECURE_SSL_REDIRECT, tests need an override to avoid 301 responses.
Production after passing tests:
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check --settings=config.settings_postgres
  python manage.py collectstatic --noinput --settings=config.settings_postgres
  sudo systemctl restart gunicorn.service

Rollback: use command printed by installer (or --list to discover backups).
