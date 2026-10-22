SUMMITDESK — VISUAL BED ALLOCATION REDESIGN

Scope:
  floorplans/templates/floorplans/visual_beds.html
  floorplans/static/floorplans/visual_beds_v120.css

The page uses the existing SummitDesk sidebar and topbar from the shared
bookings/base.html template. It does not change views, endpoints, models,
permissions, assignment validation, or database schema.

INSTALL
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v120.zip
  python3 v120_package/install_v120.py

CHECK (use your existing virtualenv and production settings)
  python manage.py check
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service

Open /staff/floorplans/3/visual-beds/ (or use the Rooms & beds menu).
If your route differs, use the existing Visual Beds navigation link.

ROLLBACK
  python3 v120_package/rollback_v120.py summitdesk_backups/visual_beds_<timestamp>
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service

A new backup folder is printed by the installer. Keep it for rollback.

SECURITY
  All bed data continues to come from existing hut-scoped staff endpoints.
  The page makes no permission changes. Guest names are inserted with
  textContent, never as HTML. CSV export keeps spreadsheet formula escaping.
  "Unassigned" is not represented as "available".
