SummitDesk v78-v82: five features in one package.
Critical issues, arrivals timeline, numbered bed details, computed daily checklist, overview.
No visible version labels on new page; old visible labels removed from Manager Operations page.
Requires v73-v77. Read-only; no migrations.

Install: unzip -o summitdesk_v78_v82.zip && python3 v78_v82_package/install_v78_v82.py
Verify: python -m py_compile floorplans/staff_hub.py floorplans/daily_workspace_v78_v82.py && python manage.py check
Manager page: /staff/floorplans/3/hub/?operations=1
Check cleaner and cross-hut access, date selection, no numbered beds, and pending assignments.
Important: bed detail 'Unassigned' means no assignment recorded, NOT free for booking.
