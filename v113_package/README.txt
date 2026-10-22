SummitDesk v113 — Real Reservation Calendar Redesign

Built against the uploaded summitdesk_source_v113.zip project source.
Replaces the existing weekly reservation timeline presentation at:
  /staff/availability/week/  (subject to your site's bookings URL prefix)

Features:
- Rooms down the left; seven dates across the top.
- Booking bars span the nights actually occupied, including reservations that started before this week.
- Overlapping bookings display on separate tracks.
- Confirmed / pending booking styles, mobile horizontal scrolling, simple date navigation.
- Existing edit and drag-to-preview-move links preserved; server confirmation still required.
- Existing hut-scoped manager/staff permissions preserved.
- No migrations, no changes to reservation services, no feature version numbers on site.

Install:
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v113.zip
  python3 v113_package/install_v113.py

Check:
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python -m py_compile bookings/calendar_timeline.py bookings/timeline_helpers_v113.py
  python manage.py check
  sudo systemctl restart gunicorn.service

Test:
- Open /staff/availability/week/ or your site's equivalent bookings-prefixed URL.
- Check bookings crossing the first/last day of the week.
- Click a booking to edit.
- Drag a booking to another room/night; verify confirmation screen (do not confirm unless intended).
- Verify access with staff users assigned to different huts.
- Check mobile horizontal scrolling.

Rollback: restore the .bak_v113_TIMESTAMP copies for both files and remove
bookings/timeline_helpers_v113.py, then run checks and restart.
