SummitDesk v58-v62 combined release (requires installed v57)

v58: CSV export of v56 severity + v57 keyword-filtered capacity warnings.
v59: room-level 7-day forecast for selected v45 start date.
v60: room-level capacity warnings.
v61: confirmed-arrival readiness planning (open cleaning tasks on arrival date, unassigned bed places).
v62: numbered-bed assignment conflicts and bed-closure conflicts.

Read-only; no migrations. This release detects conflicts only for explicitly assigned numbered beds. Unassigned bed places cannot be checked for bed-level overlap. Room capacity warnings do cover unassigned reservations.

Install: unzip -o summitdesk_v58_v62.zip; python3 v58_v62_package/install_v58_v62.py
Verify: python -m py_compile floorplans/staff_hub.py floorplans/operations_v58_v62.py; python manage.py check
Then test manager/cleaner permissions before restarting gunicorn.service.

Backups: installer creates timestamped backups of staff_hub.py and staff_hub.html.
