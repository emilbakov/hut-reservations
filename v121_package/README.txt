SummitDesk v121 — Simple availability-first staff booking form
=============================================================

Both URLs now render the SAME shared booking template:
  /staff/reservations/new/
  /staff/floorplans/<hut_id>/new-booking/

Includes:
- Default today/tomorrow availability (change dates to refresh)
- Hut-level free beds, total beds, rooms with space and nights
- Room-level bed counts and simple quantity selectors
- Selected beds and estimated price (client-side estimate only)
- Guest contact form; original backend validation is preserved
- Existing manager-only hut permissions and atomic booking service

IMPORTANT: Availability is the MINIMUM available bed count across all
nights in each room, including maintenance closures. It does NOT identify
which numbered beds are unassigned or guarantee a specific bed.

Prerequisites: v116 shared navigation, v118 booking permission fix.

Install (from Django project root):
  unzip -o summitdesk_v121.zip
  python3 v121_package/install_v121.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  python manage.py test bookings.test_staff_booking_ui_v121
  sudo systemctl restart gunicorn.service

The installer prints the timestamped backup path. To roll back:
  python3 v121_package/rollback_v121.py summitdesk_backups/booking_ui_<timestamp>
  sudo systemctl restart gunicorn.service

No migrations, no changes to booking data, services or authorization.
