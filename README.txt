SummitDesk v37 — Staff Hub Daily Overview

Adds a manager-only daily confirmed booking snapshot to the existing Staff Hub.
It preserves existing v36 links, operations, and cleaner task views.

INSTALL
1. Upload summitdesk_v37.zip to /home/deploy/hut-reservations/
2. SSH to the server, cd /home/deploy/hut-reservations
3. unzip -o summitdesk_v37.zip
4. python3 install_v37.py
5. Activate your virtualenv and PostgreSQL environment as usual.
6. python manage.py check
7. sudo systemctl restart gunicorn.service
8. Open /staff/floorplans/3/hub/

No migrations. No reservation data changes. The installer creates a backup
folder named v37_backup_YYYYMMDD_HHMMSS before changing existing files.
The installer aborts if it cannot identify the expected v27/v36 code markers.

NOTES
- Current active rooms only, same scope as v34/v35.
- Confirmed nightly value is NOT payment revenue.
- The existing hub's top occupancy figures include pending holds;
  the new snapshot is confirmed-only.
