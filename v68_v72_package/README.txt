SummitDesk v68-v72 combined upgrade. Requires v63-v67.

v68 Conflict CSV; v69 room availability CSV; v70 arrivals CSV; v71 action CSV; v72 action-priority filter.

No database migrations. All exports use existing manager-only /staff/floorplans/<hut_id>/hub/?operations=1 route.
CSV escaping uses the existing v58-v62 csv_response helper.

Install: unzip -o summitdesk_v68_v72.zip && python3 v68_v72_package/install_v68_v72.py
Check: python -m py_compile floorplans/staff_hub.py floorplans/operations_exports_v68_v72.py && python manage.py check
Verify: manager page 200 and downloads; cleaner and unrelated user must never get CSV; cross-hut access 403.
