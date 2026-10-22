SummitDesk v133 — Responsive Staff Operations (mobile phase 1)
=============================================================

Scope
-----
- Unified staff sidebar/navigation for the guest approval queue and v130-v132
  reminder pages (the existing staff shell had omitted those routes).
- Mobile sidebar uses an inert closed state, Escape and backdrop closing,
  focus cycling, breakpoint reset, and body scroll lock.
- Reservations table becomes readable guest cards on screens up to 720px,
  keeping original POST forms, CSRF tokens and confirmation behavior.
- Guest approval filters, stats and action buttons adapt to narrow screens.
- Dashboard cards fit small phones without page-level horizontal overflow.
- Weekly calendar retains sideways scrolling and adds a swipe hint.
- Touch targets are at least approximately 44px for primary actions.

Does NOT change
---------------
- Reservation authorization, state transitions, availability, notifications,
  email scheduler, database schema, or API endpoints.
- Public-facing guest booking pages (planned for a later mobile phase).

Preconditions
-------------
- SummitDesk v132 installed.
- Run installer from the directory containing manage.py.
- v116 navigation JavaScript must match the known v132 baseline; if it was
  customized, the installer refuses to overwrite it. Contact the developer
  for a merged patch rather than bypassing the check.
- Backup the production project and database before installation.

Install and verify
------------------
   unzip -o summitdesk_v133.zip
   python3 v133_package/install_v133.py
   source myprojectenv/bin/activate
   export DJANGO_SETTINGS_MODULE=config.settings_postgres
   set -a; source /etc/hut-reservations/postgres.env; set +a
   python manage.py check
   python manage.py test bookings.test_mobile_v133 bookings.test_reservation_management bookings.test_approval_dashboard_v127 bookings.test_manager_digest_preferences_v130
   python manage.py collectstatic --noinput

Then restart the existing Django service. No migrations required.
Test at 375px, 768px and desktop widths; verify navigation, requests,
reservations, dashboard and weekly calendar.

Rollback
--------
The installer prints its backup folder (summitdesk_backups/mobile_v133_...).
Use: python3 v133_package/rollback_v133.py summitdesk_backups/mobile_v133_TIMESTAMP
Rollback refuses if installed files have been edited since installation.
After rollback, collectstatic and restart the Django service.
