SummitDesk v131 — Daily Manager Email Preview & Diagnostics
===========================================================

Requires SummitDesk v130 already installed. Source-only incremental upgrade.

NEW
- /staff/settings/reminders/preview/ — manager-only read-only preview.
- Pending request totals per authorized active hut, waiting over 24 hours,
  and arrivals due within 2 days / overdue.
- Preview of the subject and text body of the next daily manager email.
- Explains why a digest is not eligible: disabled preferences, urgent-only
  waiting, already sent today, no email address, or no pending requests.
- Link from /staff/settings/reminders/.
- Never sends emails, changes reservations, or consumes the daily digest log.
- No migrations, cron/timer, or SMTP configuration changes.

1. UPLOAD FROM WINDOWS POWERSHELL
Save summitdesk_v131.zip in Downloads:
scp "$env:USERPROFILE\Downloads\summitdesk_v131.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

2. INSTALL ON UBUNTU (BACK UP YOUR PROJECT AND DATABASE FIRST)
ssh deploy@167.233.96.3
cd /home/deploy/hut-reservations
unzip -o summitdesk_v131.zip
python3 v131_package/install_v131.py

3. TARGETED TESTS ONLY (NO FULL TEST SUITE)
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
python manage.py test bookings.test_manager_digest_preview_v131 bookings.test_manager_digest_preferences_v130

If tests pass, restart your actual Django/Gunicorn service.
Open: https://YOUR_DOMAIN/staff/settings/reminders/preview/

NOTES
- Preview uses the configured SUMMITDESK_BASE_URL if present in the web
  worker; otherwise it uses a validated request origin. If neither is a
  trusted origin, links in the preview are relative. The scheduled email
  still uses its own configured SUMMITDESK_BASE_URL.
- 'Eligible' is not a guarantee of delivery. The v129 timer and SMTP
  configuration must be working independently.
- The preview only displays counts and hut names, not guest details.
- The preview does not override a manager's opt-out settings.
- This is a source-only upgrade; it does not need python manage.py migrate.

ROLLBACK
The installer prints its timestamped backup folder. To revert, first
back up your work and run:
python3 v131_package/rollback_v131.py summitdesk_backups/manager_digest_preview_<timestamp>
Rollback refuses to overwrite any v131 file modified since installation.
