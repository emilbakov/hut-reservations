SummitDesk v138 — REVISED Property Calendar (one hut, all rooms)
==============================================================

This is the revised Property Calendar ZIP with visible per-cell Book buttons.
This is NOT the earlier all-huts v138 ZIP. Do not install both packages.

Scope:
- /staff/floorplans/<hut_id>/calendar/ now opens the selected hut's monthly overview.
- All rooms in that hut appear, including inactive rooms marked inactive.
- Room-level free beds reflect holding reservations and distinct maintenance closures.
- Pending/confirmed bookings appear; cancelled bookings do not consume capacity.
- Mixed-hut reservations consume capacity but their guest details are hidden.
- A prominent + Book button appears inside each future room/date cell with free beds.
- Full, inactive and past-date cells have no Book button.
- + Book opens the existing validated staff booking form with room, hut and date selected.
- "Detailed timeline" opens the ORIGINAL interactive timeline with ?view=timeline.
- The timeline retains its existing drag/drop transfers, numbered beds and filters.
- The separate Reservation Calendar is NOT modified.
- No database migrations, new URLs, booking write logic or staff nav changes.

Deployment, one step at a time:
1. Upload summitdesk_v138_property.zip to /home/deploy/hut-reservations/
2. cd /home/deploy/hut-reservations
   unzip -o summitdesk_v138_property.zip
   python3 v138_property_package/install_v138_property.py --check
3. Only if preflight OK:
   python3 v138_property_package/install_v138_property.py
4. source myprojectenv/bin/activate
   python manage.py test floorplans.test_property_calendar_v138 --settings=config.settings
   python manage.py test bookings.test_availability_calendar --settings=config.settings
5. set -a; source /etc/hut-reservations/postgres.env; set +a
   python manage.py check --settings=config.settings_postgres
   python manage.py collectstatic --noinput --settings=config.settings_postgres
   sudo systemctl restart gunicorn.service
   sudo systemctl status gunicorn.service --no-pager
6. Browser check: /staff/floorplans/<your-hut-id>/calendar/
   Check Monthly overview and Detailed timeline; create/edit links; mobile scrolling.

ROLLBACK
The installer prints the exact backup directory. For example:
  python3 v138_property_package/rollback_v138_property.py --list
  python3 v138_property_package/rollback_v138_property.py --check summitdesk_backups/property_calendar_v138_TIMESTAMP
  python3 v138_property_package/rollback_v138_property.py summitdesk_backups/property_calendar_v138_TIMESTAMP
  sudo systemctl restart gunicorn.service
Rollback refuses to overwrite files changed since v138 installation.

PREFLIGHT
Installer requires exact SHA256 hashes of the uploaded v126 production snapshot's
property calendar files. If either has been modified, it refuses to install.
The installer also refuses if the earlier all-hut v138 implementation is present.

LOCAL VERIFICATION
Python compileall: PASS
Installer and rollback dry-run against local snapshot: PASS
Django: 8 targeted tests + 29 regression tests PASS locally with SQLite
Local test environment omits staticfiles (not bundled in uploaded virtualenv).
See TEST_RESULTS.txt. Re-run with your real server settings before restart.
