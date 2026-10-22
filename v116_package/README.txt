SummitDesk v116 — Unified Front Desk (Little Hotelier-inspired workflow)
=======================================================================
One release, no database changes. Built against the uploaded source and v115.

What changes
- One shared SummitDesk staff sidebar/topbar on booking-management and hut-management pages.
- Property switcher only lists huts assigned to the logged-in manager.
- Cleaner accounts see only their own hut dashboard and assigned cleaning tasks.
- Staff navigation: Overview, calendar, reservations, arrivals/departures, new booking,
  hut operations, rooms/beds, housekeeping, team, finances, reports, communications.
- Current page highlighted; search, new booking, and responsive mobile menu.
- Removes duplicate old sidebars on hut staff pages without rewriting booking workflows.
- Public booking pages remain unchanged. No new permissions or endpoints.
- No website version badges or labels introduced.

Requirements
- v115 installed; Django source in /home/deploy/hut-reservations.
- Server can run Python 3 and existing Django virtual environment.

Windows PowerShell upload
  scp "$env:USERPROFILE\Downloads\summitdesk_v116.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

Ubuntu install
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v116.zip
  python3 v116_package/install_v116.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service

Important live checks
- /staff/dashboard/ : staff sidebar, hut switcher, real dashboard figures
- /staff/availability/week/ : v113 timeline + v114 quick view still work
- /staff/floorplans/3/calendar/ : old duplicate sidebar gone, calendar works
- /staff/floorplans/3/hub/ : housekeeping, team and operations links
- /staff/reservations/ and /staff/finances/ : search/forms still work
- Mobile: menu opens/closes, Esc closes, horizontal calendar scrolling
- Log in as a cleaner: no booking/finance links; hut isolation maintained
- Public booking pages: unchanged guest navigation

Rollback
  python3 v116_package/rollback_v116.py summitdesk_backups/shared_shell_TIMESTAMP
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service
The installer prints the exact backup path. The rollback script uses that path.

No data migrations or reservation modifications. Run checks before restarting.
