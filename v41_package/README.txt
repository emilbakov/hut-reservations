SummitDesk v41 — Operations Alert Severity Filters
Prerequisite: v40 installed and working.
Read-only, manager-only, hut-scoped. Adds severity dropdown to the existing v39 alerts panel; the v40 summary remains unchanged.
Install from project root: unzip -o summitdesk_v41.zip && python3 v41_package/install_v41.py
Verify: python -m py_compile floorplans/staff_hub.py floorplans/alert_filters_v41.py && python manage.py check
Restart: sudo systemctl restart gunicorn.service
Test: /staff/floorplans/3/hub/?alert_level=urgent and ?alert_level=warning
No migrations. No database writes. Backup files are timestamped.
