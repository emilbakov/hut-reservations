# Floor Plan V5 — Room reservation details

Adds a read-only reservation list to each room in the V4 availability map.

## Requirements
- V4 floorplans app installed and working (including `availability_map` and `availability` URL routes).
- Existing `bookings.models.ReservationItem`, `Reservation`, `Room`, `Hut` models.

## Deploy (from project root)
1. Back up your existing files:
   `cp floorplans/views.py floorplans/views.py.bak.v4`
   `cp floorplans/templates/floorplans/availability_map.html floorplans/templates/floorplans/availability_map.html.bak.v4`
2. Extract ZIP to a temporary folder (e.g. `unzip -o floorplan_reservations_v5.zip -d floorplan_v5`).
3. Copy `floorplan_v5/floorplans/views.py` to `floorplans/views.py`.
4. Copy `floorplan_v5/floorplans/templates/floorplans/availability_map.html` to `floorplans/templates/floorplans/availability_map.html`.
5. Add the route in `URLS_ADD.txt` to `floorplans/urls.py`. Preserve existing routes and the `app_name = "floorplans"` declaration.
6. Run `python manage.py check`, then restart your actual Gunicorn service.

No database migration needed. The endpoint is staff-only and hut-scoped, includes pending and confirmed overlapping reservations, and excludes cancelled reservations. It uses [check_in, check_out) overlap rules. Guest names are shown only to authorized staff. Only superusers receive Django admin links; other managers can view reservation information without being sent to an admin page they may not have permission to access.

Note: Availability comes from the existing free_beds service. If that service applies bed closures or assignments, the displayed occupied count may not equal the sum of overlapping reservation item quantities. This list is not a per-bed occupancy assignment.
