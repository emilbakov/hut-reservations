SummitDesk v132 — Reminder Email History & CSV Export
====================================================

Requires v131 installed. Incremental source-only upgrade.

NEW
- /staff/settings/reminders/history/ — authenticated, manager-only send history.
- Preset filters: 7, 30 (default), 90, 365 days, or all history.
- Summary counts of recorded sends, hut summaries, and requests reported.
- Paginated history table, 20 entries per page.
- CSV export of ALL records matching the selected period (not just one page).
- UTF-8 CSV with Excel BOM; recipient fields protected against spreadsheet
  formula injection.
- Links from v130 reminder settings and v131 preview.
- GET-only, no-store responses, only the logged-in manager's records.
- No guest PII, guest tokens, reservation changes, mail sends, or log writes.
- Does not require a migration or changes to the v129 email timer.

IMPORTANT: "Recorded as sent" means the configured mail backend accepted the
message; it does not guarantee that an email reached the manager's inbox.

1. UPLOAD FROM WINDOWS POWERSHELL
Save summitdesk_v132.zip to Downloads:
scp "$env:USERPROFILE\Downloads\summitdesk_v132.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

2. INSTALL ON UBUNTU (BACK UP PROJECT AND DATABASE FIRST)
ssh deploy@167.233.96.3
cd /home/deploy/hut-reservations
unzip -o summitdesk_v132.zip
python3 v132_package/install_v132.py

3. TARGETED TESTS ONLY — NO FULL SUITE
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
python manage.py test bookings.test_manager_digest_history_v132 bookings.test_manager_digest_preview_v131 bookings.test_manager_digest_preferences_v130

If tests pass, restart the real Django/Gunicorn service.
Open: https://YOUR_DOMAIN/staff/settings/reminders/history/

ROLLBACK
The installer prints its timestamped backup folder. To revert, run:
python3 v132_package/rollback_v132.py summitdesk_backups/manager_digest_history_<timestamp>
Rollback refuses to overwrite any v132 file changed since installation.

NOTES
- Installer preflights all expected source anchors and compiles Python before
  writing anything. It refuses a second installation and creates a backup.
- Do not re-run the installer on a project already running v132.
- Requires v129/130/131 tables and modules already installed.
- No changes to SMTP credentials or scheduler are needed.
