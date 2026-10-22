SummitDesk v130 — Manager Daily Email Reminder Preferences
===========================================================
Requires v129 already installed. v130 does not replace the whole project.

WHAT'S NEW
- Personal manager page at /staff/settings/reminders/ (also linked from
  the Guest Reservation Requests dashboard).
- Managers can turn daily digest emails on/off, or choose urgent-only mode.
- Urgent = at least one pending guest reservation waiting >24 hours or with
  arrival within 2 days / overdue. In urgent-only mode the email still
  summarizes all pending requests in the manager's authorized huts.
- Last 10 successfully submitted email digest logs, visible only to the
  logged-in manager. No guest names or access tokens are displayed.
- Default behavior unchanged for managers who have not configured settings.
- No changes to the timer, SMTP settings, bookings, payments, or bed inventory.
- Migration 0015 creates one small preferences table.

1. WINDOWS POWERSHELL UPLOAD (save ZIP in Downloads first)
scp "$env:USERPROFILE\Downloads\summitdesk_v130.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

2. INSTALL ON UBUNTU (back up project AND database first)
ssh deploy@167.233.96.3
cd /home/deploy/hut-reservations
unzip -o summitdesk_v130.zip
python3 v130_package/install_v130.py

3. PRODUCTION ENVIRONMENT + TARGETED TESTS ONLY (NO FULL TEST SUITE)
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a

python manage.py migrate --noinput
python manage.py check
python manage.py test bookings.test_manager_digest_preferences_v130 bookings.test_manager_digest_v129

After tests pass, restart your actual Django/Gunicorn service if necessary.

IMPORTANT
- If you have not enabled the v129 daily digest timer, v130 does NOT enable it.
- Turning reminders off does not stop previously sent emails or change
  pending reservations. Settings affect subsequent scheduled runs.
- A v129 daily digest that has already been logged as sent will not be
  resent that day even if the user changes their preferences.
- Do not re-run the installer after success; it intentionally refuses
  to overwrite existing v130 files.
- Installer creates a dated code backup under summitdesk_backups/.
- Keep database backups separately before migrations.

ROLLBACK
Before restoring code, and only if no later migrations depend on v130,
back up your database and reverse the schema migration:
  python manage.py migrate bookings 0014 --noinput
Then restore original source files using the printed backup directory:
  python3 v130_package/rollback_v130.py summitdesk_backups/manager_preferences_<timestamp>
The rollback refuses to overwrite files modified after installation.

TESTING
See v130_package/TEST_RESULTS.txt for local verification details.
