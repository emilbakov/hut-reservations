# V8 — permanent physical bed markers

1. Back up your database and current `floorplans/models.py` and `floorplans/templates/floorplans/visual_beds.html` before installing.
2. Copy the `floorplans/` files into the matching paths in your project. This includes the updated `models.py`, `visual_beds.html`, new `bed_markers.py`, `bed_layout.html` and the management command directory.
3. Add to `floorplans/urls.py`:

    from . import bed_markers as bm8

    path('<int:hut_id>/bed-layout/', bm8.layout_page, name='bed_layout'),
    path('<int:hut_id>/rooms/<int:room_id>/markers/', bm8.markers, name='bed_markers'),
    path('<int:hut_id>/rooms/<int:room_id>/markers/save/', bm8.save_markers, name='save_bed_markers'),

4. Activate the existing virtual environment, then run:

    python manage.py makemigrations floorplans
    python manage.py migrate
    python manage.py backfill_bed_markers
    python manage.py check

5. Restart your actual Gunicorn service. Open `/staff/floorplans/3/bed-layout/` to edit stable positions and `/staff/floorplans/3/visual-beds/` to view assignments.

Notes:
- No changes to `bookings/services.py`, bed assignment logic or reservations.
- V8 creates a new `BedMarker` table, keyed by physical `Bed.id`. A database migration IS required.
- Existing coordinate-only markers are mapped once, in saved order to beds sorted by number. This cannot prove historical identity; visually review placements after migration.
- Missing Bed records must be initialized through V6 before running the backfill. Rerun the command after initialization if needed.
- The old floorplan editor still saves coordinate-only marker layouts; for permanent bed position editing use the new V8 bed-layout page. Editing legacy bed markers may not update permanent positions.
- Always test on staging first. No deployment/runtime tests were run against your server.
