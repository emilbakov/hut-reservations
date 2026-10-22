SummitDesk — Legacy test compatibility fixes

Purpose:
  Fix four outdated test assertions after the public booking, dashboard,
  and authorization changes. No application code or database changes.

Changes:
  bookings/tests.py
    test_search_shows_rooms: expect "4 available for your stay"
    test_staff_dashboard_shows_occupancy: expect "Beds occupied today"
    test_dashboard_displays_month_for_staff: expect "October 2026 at a glance"
  bookings/test_manual_booking.py
    test_nonstaff_denied: expect HTTP 403 and zero reservations

The two old floorplans.backup import errors are not changed by this patch.
The installer checks whether floorplans/backup exists and warns if it does.
If absent, the import errors may have been from a previous discovery run.

Install from project root (after uploading ZIP):
  unzip -o summitdesk_test_fixes.zip
  python3 summitdesk_test_fix_package/install_test_fixes.py

Run tests in existing virtualenv with configured PostgreSQL settings/env:
  python manage.py test bookings.test_manual_booking bookings.tests
  python manage.py test

No migrations, collectstatic, or Gunicorn restart required.

Rollback using the exact backup directory printed by installer:
  python3 summitdesk_test_fix_package/rollback_test_fixes.py summitdesk_backups/test_fixes_TIMESTAMP
