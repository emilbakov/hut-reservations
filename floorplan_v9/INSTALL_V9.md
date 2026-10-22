# Floor Plan V9 — Drag-and-drop guest-to-bed assignment

V9 replaces only `floorplans/templates/floorplans/visual_beds.html`. It reuses V6 assignment endpoints and V8 stable BedMarker coordinates. No migrations or URL changes.

## Install

1. Back up your existing `floorplans/templates/floorplans/visual_beds.html`.
2. Copy the file from this archive to `floorplans/templates/floorplans/visual_beds.html`.
3. Run Django checks with the **same PostgreSQL settings/environment as Gunicorn**.
4. Restart Gunicorn and hard-refresh `/staff/floorplans/<hut_id>/visual-beds/`.

Example on the server, assuming the ZIP is in `/home/deploy/hut-reservations`:

```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_drag_assign_v9.zip -d floorplan_v9
cp floorplans/templates/floorplans/visual_beds.html floorplans/templates/floorplans/visual_beds.html.backup.v8
cp floorplan_v9/floorplans/templates/floorplans/visual_beds.html floorplans/templates/floorplans/
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a
source /etc/hut-reservations/postgres.env
set +a
python manage.py check
sudo systemctl restart gunicorn.service
```

## Use

Choose room and date range, press Show beds. Drag a reservation chip onto a numbered bed. Alternatively, select a reservation from the dropdown and click a bed. With no reservation selected, click a bed to inspect assignments and unassign. Server-side V6 validation remains authoritative.

## Notes

- No changes to booking records or physical bed IDs from the installation itself.
- Gray/unassigned is NOT guaranteed free; room-level unallocated bookings still count.
- Existing V6 assignment endpoint enforces conflict and maintenance rules. This interface does not add server-side safeguards.
- Drag and drop is for desktop; select-and-click works on touch/keyboard.
