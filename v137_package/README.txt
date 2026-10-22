SummitDesk v137 — Calendar Reservation Form Redesign
====================================================

This version improves the staff New Reservation / Edit Reservation form used at:
/staff/availability/new/?check_in=YYYY-MM-DD&room=ID&hut=SLUG
/staff/availability/edit/<code>/

Scope:
- Changes ONLY bookings/templates/bookings/calendar_booking_form.html
- Adds bookings/test_calendar_form_ui_v137.py
- No model, view, URL, database, permission, service or email changes
- Keeps existing GET prefill for dates/room and existing POST behavior
- Retains guest read-only details on the edit page
- New responsive layout, summary, clearer form validation
- The summary does NOT imply live availability; existing server checks remain authoritative

INSTALL — ONE STEP AT A TIME
----------------------------
From Windows PowerShell:
scp "$env:USERPROFILE\Downloads\summitdesk_v137.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

On Ubuntu:
cd /home/deploy/hut-reservations
unzip -o summitdesk_v137.zip
python3 v137_package/install_v137.py --check

If preflight OK:
python3 v137_package/install_v137.py

Run targeted tests (development settings):
source myprojectenv/bin/activate
python manage.py test bookings.test_calendar_form_ui_v137 bookings.test_calendar_actions --settings=config.settings

Then production checks:
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check --settings=config.settings_postgres
python manage.py collectstatic --noinput --settings=config.settings_postgres
sudo systemctl restart gunicorn.service
sudo systemctl status gunicorn.service --no-pager

ROLLBACK
--------
The installer automatically backs up the ORIGINAL form template in
summitdesk_backups/calendar_form_v137_TIMESTAMP and prints the exact path.

List backups:
python3 v137_package/rollback_v137.py --list

Preview a rollback without changing files:
python3 v137_package/rollback_v137.py --check summitdesk_backups/calendar_form_v137_TIMESTAMP

Restore (requires the installed template and test file to be unchanged):
python3 v137_package/rollback_v137.py summitdesk_backups/calendar_form_v137_TIMESTAMP

After rollback, run production check and restart Gunicorn.
The rollback refuses unexpected modifications to prevent data loss.

TEST STATUS
-----------
- Installer and rollback can be verified locally without Django.
- Django integration tests MUST be run on your Ubuntu server.
- Previews use illustrative guest and hut information.

Note: the example link with check_in=2026-10-02 points to a past date
(as of 2026-10-22). Select future dates for actual new reservations.
