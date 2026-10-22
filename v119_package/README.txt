SUMMITDESK PROPERTY DASHBOARD REDESIGN
======================================

One focused update: /staff/floorplans/<hut_id>/hub/

The existing SummitDesk sidebar/topbar remains in place. The property hub
becomes a front-desk dashboard with:
 - Four clear operational KPIs (manager) or assigned cleaning KPIs (cleaner)
 - Seven-night confirmed/pending bed-place forecast (manager)
 - Today's cleaning tasks
 - Operations alerts, confirmed booking snapshot, and property shortcuts
 - Original advanced forecast, CSV, capacity and alert widgets preserved
   inside a collapsed "Advanced reports & exports" section.

Manager-only links stay manager-only. Cleaner access is not broadened.
Existing booking, calendar, reports and backend view are untouched.
No database migrations, no artificial reservation data, no visible versions.

PREREQUISITES
 - v116 shared SummitDesk navigation installed
 - v118 New Booking permission fix installed

INSTALL (from Django project root):
 unzip -o summitdesk_v119.zip
 python3 v119_package/install_v119.py

CHECK (activate your virtualenv and environment first):
 python manage.py check
 python manage.py test floorplans.test_property_dashboard_v119
 python manage.py collectstatic --noinput
 sudo systemctl restart gunicorn.service

Open /staff/floorplans/3/hub/ and test as a hut manager and cleaner.

ROLLBACK:
 The installer prints a backup directory under summitdesk_backups.
 From the Django project root:
 python3 v119_package/rollback_v119.py summitdesk_backups/property_dashboard_<timestamp>
 python manage.py collectstatic --noinput
 sudo systemctl restart gunicorn.service

The original template is backed up and can be restored byte-for-byte.
