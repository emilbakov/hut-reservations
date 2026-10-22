SummitDesk v63-v67 combined release
Requires v58-v62 installed. No migrations. Read-only.
v63 Reservation conflict dashboard (numbered-bed and room-capacity warnings)
v64 Room-level seven-night availability calendar (counts, not bed-specific availability)
v65 Arrival preparation board
v66 Prioritized manager action center
v67 Dedicated responsive Manager Operations workspace
URL: /staff/floorplans/<hut_id>/hub/?operations=1
Uses existing staff_hub URL and its manager access check. No URL changes.
Install: unzip -o summitdesk_v63_v67.zip; python3 v63_v67_package/install_v63_v67.py
Verify: python -m py_compile floorplans/staff_hub.py floorplans/manager_operations_v63_v67.py; python manage.py check
Manager should see operations page; cleaner should see original hub; unrelated user should receive 403.
