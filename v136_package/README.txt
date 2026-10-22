SUMMITDESK v136 — MONTHLY ROOM AVAILABILITY REDESIGN
==================================================

Scope
-----
Updates only bookings/templates/bookings/availability_calendar.html.
Adds a focused UI regression test: bookings/test_availability_ui_v136.py.
No migrations, view changes, URL changes, booking logic changes, or staff permission changes.
The weekly drag-and-drop timeline remains unchanged.

This version redesigns the MONTHLY staff page at /staff/availability/.

Preflight (no changes)
----------------------
cd /home/deploy/hut-reservations
unzip -o summitdesk_v136.zip
python3 v136_package/install_v136.py --check

Install (automatically backs up the old template)
------------------------------------------------
python3 v136_package/install_v136.py

The installer prints a unique backup directory such as:
  summitdesk_backups/availability_v136_20261022_210000_123456
Copy the ACTUAL printed path for rollback; do not type the example timestamp.

Test (before production restart)
--------------------------------
source myprojectenv/bin/activate
python manage.py test bookings.test_availability_ui_v136 bookings.test_availability_calendar --settings=config.settings

Production verification
-----------------------
set -a
source /etc/hut-reservations/postgres.env
set +a
python manage.py check --settings=config.settings_postgres
python manage.py collectstatic --noinput --settings=config.settings_postgres
sudo systemctl restart gunicorn.service
sudo systemctl status gunicorn.service --no-pager

Rollback options
----------------
1. List available backups (does not change files):
   python3 v136_package/rollback_v136.py --list

2. Preview/verify a specific rollback (does not change files):
   python3 v136_package/rollback_v136.py --check summitdesk_backups/availability_v136_ACTUAL_TIMESTAMP

3. Restore the previous monthly calendar and remove the v136 test:
   python3 v136_package/rollback_v136.py summitdesk_backups/availability_v136_ACTUAL_TIMESTAMP

   Then verify Django and restart Gunicorn:
   python manage.py check --settings=config.settings_postgres
   sudo systemctl restart gunicorn.service

SAFETY
------
* The installer checks the original calendar SHA256 against the uploaded production snapshot.
* It refuses to overwrite changed/customized calendars and existing v136 tests.
* It backs up the original before writing and verifies every written file.
* If the installation fails mid-write, it restores the original template.
* Rollback verifies installed file hashes before restoring, so it will not silently
  discard changes made after v136 installation.
* Rollback never changes database records.
* No need to run migrations.
* If a rollback refuses due to later edits, manually review/diff those changes first.

PREVIEWS
--------
preview_v136_desktop.png and preview_v136_mobile.png are illustrative.
preview_v136.html is a standalone static demo, not a live booking application.
The real page uses the database's actual huts, rooms, reservations, and prices.
