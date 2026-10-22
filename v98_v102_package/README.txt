SummitDesk v98-v102 — UI/UX redesign, one combined package
Prerequisite: v93-v97 installed.

v98 Cleaner dashboard: essential KPI cards and clear visual hierarchy.
v99 Five-workspace desktop sidebar: Overview, Reservations, Availability, Housekeeping, Reports.
v100 Better availability calendar readability and sticky room labels.
v101 Mobile navigation drawer, larger touch targets, responsive cards.
v102 Consistent spacing, typography, colors, focus states and print view.

Website labels do not contain version numbers. Existing sections, filters, links,
exports and server-side access controls are retained. This upgrade edits only the
manager_operations_v63_v67.html template. No migrations, no backend changes.

Upload (Windows PowerShell):
scp "$env:USERPROFILE\Downloads\summitdesk_v98_v102.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

Install (Ubuntu, from project root):
unzip -o summitdesk_v98_v102.zip
python3 v98_v102_package/install_v98_v102.py

Verify (after activating your virtualenv and loading your existing environment):
python manage.py check
sudo systemctl restart gunicorn.service

Test:
/staff/floorplans/3/hub/?operations=1
/staff/floorplans/3/hub/?operations=1#availability
/staff/floorplans/3/hub/?operations=1#housekeeping
Try mobile width and test each of five navigation tabs.
Confirm manager-only and cross-hut restrictions remain unchanged.

Rollback: restore the timestamped .bak_v98_v102_* template and restart Gunicorn.

The page uses progressive enhancement: if JavaScript is disabled, all existing
sections stay visible as before. No reservation data is modified.
