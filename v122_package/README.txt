SummitDesk v122 — Small bed availability calendar on both New Booking pages
==========================================================================

Both staff booking URLs use the shared v121 template:
  /staff/reservations/new/
  /staff/floorplans/<hut_id>/new-booking/

A compact monthly calendar now appears above the room quantities in step 2.
Each day shows how many beds are free ACROSS ALL ACTIVE ROOMS for that night:
  green: 3 or more beds, amber: 1-2 beds, red: none.
Click a date to check a one-night stay. Change check-out for longer stays.
Previous/next arrows change the calendar month, preserving booking dates.

The calendar uses the same reservation statuses and closure rules as the
booking service. It does not promise a numbered bed, does not reserve a bed,
and does not replace the full-stay room availability check when saving.
Data is scoped to the manager's authorized hut. No public API is added.

Prerequisite: v121 installed and working.

Install from Django root:
  unzip -o summitdesk_v122.zip
  python3 v122_package/install_v122.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  python manage.py test bookings.test_booking_calendar_v122
  sudo systemctl restart gunicorn.service

Rollback:
  python3 v122_package/rollback_v122.py summitdesk_backups/booking_calendar_<timestamp>
  sudo systemctl restart gunicorn.service

No migrations, no new permissions, no changes to existing booking service.
