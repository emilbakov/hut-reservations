SummitDesk v118 — New Booking / New Reservation 403 fix

Prerequisites: v116 shared navigation and v117 staff login installed.

Fixes:
- Global New Reservation accepts an authorized hut slug OR numeric ID on GET.
- Assigned hut managers can create bookings without Django's unrelated is_staff flag.
- Property New Booking uses login_required plus the existing permitted_hut check.
- Navigation exposes the New Booking action to managers without is_staff.
- A successful nonstaff manager booking returns to their hut dashboard.
- Foreign huts and cleaners remain blocked; all existing capacity checks remain.

Install (from /home/deploy/hut-reservations):
  unzip -o summitdesk_v118.zip
  python3 v118_package/install_v118.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  python manage.py test bookings.test_booking_access_v118
  sudo systemctl restart gunicorn.service

If the test database cannot be created with the PostgreSQL production user,
run the tests in an isolated test database with appropriate permissions;
never grant CREATE DATABASE privileges casually to production credentials.

Rollback: use the exact backup directory printed by installer:
  python3 v118_package/rollback_v118.py summitdesk_backups/booking_403_<timestamp>
  sudo systemctl restart gunicorn.service

No migrations. No static changes. No version labels in website UI.
