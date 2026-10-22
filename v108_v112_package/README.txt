SummitDesk v108-v112 — Availability Calendar Usability
Requires v103-v107 installed. No database migrations.

v108 Search rooms directly within the calendar.
v109 Filter rooms by displayed availability status.
v110 Toggle comfortable / compact calendar rows.
v111 Sticky day headings while scrolling the calendar.
v112 One-click filter reset and matching room count.

All five features are interface-only. No website version labels.
The original server-rendered table remains if JavaScript is unavailable.
Statuses are inherited from existing server calculations, not recalculated.

Install:
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v108_v112.zip
  python3 v108_v112_package/install_v108_v112.py

Verify:
  python manage.py check
  sudo systemctl restart gunicorn.service

Test:
  /staff/floorplans/3/hub/?operations=1#availability
  Search room names, filter by status, toggle compact view, clear filters.
  Test desktop and phone widths; check manager/cleaner permissions.
