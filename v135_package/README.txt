SummitDesk v135 — Staff Dashboard UI/UX Redesign
=================================================

Scope
-----
A visual-only upgrade to /staff/dashboard/. The existing staff navigation,
reservation logic, permission checks, hut selection, and data calculations
are unchanged. No migrations or changes to Django views or settings.

Changes
-------
- Modern alpine overview using existing SummitDesk green/lime design.
- Better hierarchy for today's reserved beds, arrivals, departures, pending bookings.
- Upcoming arrivals shown as a readable table on desktop and stacked cards on mobile.
- Clear quick links to calendar, check-in/out, room availability, requests,
  financial reports, stay history, messages, and hut workspaces.
- Monthly occupancy, bed-nights and projected revenue with a progress bar.
- Responsive layout, keyboard focus states, and reduced-motion support.
- Maintains v133 dashboard mobile-test marker and 'New reservation' text.

Compatibility
-------------
Built from the supplied production snapshot (including v133/v134 updates).
The installer verifies the original dashboard SHA256 and refuses to overwrite
an unexpected or modified dashboard. The ZIP does not contain a full project,
credentials, guest data, or database dumps.

Preview
-------
preview_v135.html is a standalone illustrative rendering of the proposed
v135 dashboard. Its guest names and numbers are fictional. It uses a simplified
preview navigation shell; the installed page uses your existing staff shell.
preview_v135_desktop.png and preview_v135_mobile.png are screenshots of that
illustrative preview, not screenshots of your live site.

Install (Ubuntu, project root)
-----------------------------
cd /home/deploy/hut-reservations
unzip -o summitdesk_v135.zip
python3 v135_package/install_v135.py --check
python3 v135_package/install_v135.py

Load production env variables for Django commands:
source myprojectenv/bin/activate
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check --settings=config.settings_postgres

Run targeted tests against a disposable test database:
python manage.py test bookings.test_dashboard_ui_v135 bookings.test_mobile_v133 bookings.test_menager_access --settings=config.settings_postgres

When all checks pass:
sudo systemctl restart gunicorn.service

Open /staff/dashboard/ and check desktop/mobile. collectstatic is NOT needed
because the CSS is inside the dashboard template.

Rollback
--------
The installer prints a backup directory, for example:
  summitdesk_backups/dashboard_v135_YYYYMMDD_HHMMSS_microseconds

From the project root, run:
  python3 v135_package/rollback_v135.py summitdesk_backups/dashboard_v135_...
  sudo systemctl restart gunicorn.service

Rollback refuses if the installed dashboard or test file was modified after
installation, to avoid destroying later edits.

Known limitation
----------------
The v135 installer checks an exact dashboard baseline. If you customized the
dashboard since creating the ZIP, it will refuse to install; do not bypass the
check. Contact us with the updated dashboard file so we can merge changes.
