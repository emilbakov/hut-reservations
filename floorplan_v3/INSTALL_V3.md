# Floor Plan Editor V3 — Visual bed layouts

Adds a visual 8 × 6 bed-position grid for each room. **These are illustrative markers only**: the existing bookings app reserves quantities per room, not specific bed IDs. Do not use this UI to promise individual bed availability.

## Upgrade from V2
1. Back up the PostgreSQL database and the `floorplans` directory.
2. Copy `floorplans/` over your existing `floorplans/` app. Do not replace your `bookings` Python files.
3. Activate your project's virtual environment and database environment settings.
4. Run `python manage.py showmigrations floorplans`, `python manage.py makemigrations --check --dry-run floorplans`, `python manage.py migrate floorplans`, and `python manage.py check`.
5. Optionally copy `manual_booking_floorplan.html` to `bookings/templates/bookings/manual_booking.html` after backing up your current template. If your current booking template has newer features, keep it; V3 bed editing works independently.
6. Restart Gunicorn only after checks pass.

Editor: `/staff/floorplans/<hut_id>/edit/`. Click **Beds** inside a room, click cells to arrange bed markers, **Done**, then **Save floor plan**. The server validates marker coordinates and limits marker count to room capacity.

Limitations: 48 visual positions per room; rooms with capacity over 48 cannot map all beds. Changes to the room's capacity do not automatically delete saved markers; review layouts after capacity changes. No guest-to-bed assignment, per-bed availability, or bed-level reservation changes. Test on staging before production.
