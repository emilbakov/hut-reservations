SummitDesk v73-v77 (combined, read-only)
Prerequisite: v68-v72 installed and verified.
v73 Keyword search for manager actions
v74 Day filter within selected 7-day forecast
v75 Filtered action counts by priority
v76 Filtered CSV export (same dataset as screen)
v77 Sort by priority or earliest date

Install: unzip -o summitdesk_v73_v77.zip && python3 v73_v77_package/install_v73_v77.py
Check: python -m py_compile floorplans/staff_hub.py floorplans/operations_filters_v73_v77.py && python manage.py check
Test manager URL /staff/floorplans/3/hub/?operations=1
CSV: ?operations=1&action_level=conflicts&action_q=room&operations_export=actions
Test manager/cleaner/unrelated hut access; no database migrations.
