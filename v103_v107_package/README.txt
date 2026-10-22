SummitDesk v103-v107: Availability Calendar UI/UX
Requires v98-v102. No migrations or reservation changes. Template-only progressive enhancement.

v103 Clear room availability states and legend
v104 Previous/next week navigation (server-side date selection)
v105 Click room for numbered bed assignment details
v106 Mobile-friendly horizontally scrollable calendar and touch targets
v107 Cleaner labels, explanatory states and accessible room selection

No version labels are shown on the website.

Install:
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v103_v107.zip
  python3 v103_v107_package/install_v103_v107.py

Verify:
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  sudo systemctl restart gunicorn.service

Open /staff/floorplans/3/hub/?operations=1#availability
Check previous/next week, room selection, numbered bed detail and mobile scroll.
The original table remains available when JavaScript is disabled.
Note: room-level free counts are NOT proof a particular numbered bed is available.
