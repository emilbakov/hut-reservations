SummitDesk v139 - Property Calendar today focus

Requires v138 property book installed. No database migrations.
Changes only floorplans/templates/floorplans/property_calendar_v138.html
Adds Today highlight and automatic horizontal scroll to today when current month is displayed.
Previous/next month stay at initial horizontal position. Booking buttons and all room availability calculations remain unchanged.

From project root:
  python3 v139_today_package/install_v139_today.py --check
  python3 v139_today_package/install_v139_today.py

After installation, run tests with your existing test configuration and check the Property Calendar in browser.

Rollback path is printed by installer.
