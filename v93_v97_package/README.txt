SummitDesk v93-v97: five updates in one package. Requires v88-v92.
v93 Sort critical issues by date or title.
v94 Sort arrival readiness by date or outstanding work.
v95 Filter-aware attention summary counts.
v96 Export combined filtered issues and readiness CSV.
v97 Reset issue and readiness filters.
No migrations, no writes to reservations, no visible website version numbers.
Install: unzip -o summitdesk_v93_v97.zip && python3 v93_v97_package/install_v93_v97.py
Verify: python -m py_compile floorplans/staff_hub.py floorplans/operations_summary_v93_v97.py && python manage.py check
Test /staff/floorplans/3/hub/?operations=1
Test /staff/floorplans/3/hub/?operations=1&daily_tools_export=summary
Check manager-only and cross-hut restrictions.
