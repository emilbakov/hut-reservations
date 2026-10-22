SUMMITDESK PUBLIC SITE — HOMEPAGE AND HUT DIRECTORY

One focused release: / becomes the public mountain-stay homepage, /huts/
becomes a searchable hut directory. The former role-selection page remains
available at /welcome/. Staff login and all existing booking/staff endpoints
are preserved.

Search by hut name or location, optionally select both dates and the number
of beds needed. When dates are valid, the directory uses the existing
bookings.services.free_beds function (confirmed + pending bookings and bed
closures), and shows huts with enough space for the ENTIRE selected stay.
The hut detail page receives the selected check-in/check-out dates.

IMPORTANT: This is a public discovery interface, NOT a new booking engine.
The existing booking page continues to validate availability on submission.
No fictitious huts, prices, reviews or reservation counts are inserted.

Requirements: existing SummitDesk source, staff login (v117) installed,
existing adventure-hero.avif static asset.

Install:
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v124.zip
  python3 v124_package/install_v124.py

Then in your configured Django environment:
  python manage.py check
  DJANGO_SETTINGS_MODULE=config.settings python manage.py test bookings.test_public_site_v124
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service

Rollback (use the exact path printed by installer):
  python3 v124_package/rollback_v124.py summitdesk_backups/public_site_TIMESTAMP
  python manage.py check
  sudo systemctl restart gunicorn.service

This release changes one existing file (bookings/urls.py), adds new public
views, templates, CSS and tests. No migrations and no staff permission changes.
