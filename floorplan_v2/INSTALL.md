# Floor plan editor — installation

This release adds a separate `floorplans` Django app, keeping existing booking services untouched.

1. Copy `floorplans/` into the project root beside `bookings/`.
2. Add `"floorplans"` to `INSTALLED_APPS` in the ACTIVE Django settings module.
3. In the project-level URL configuration (the file that includes `bookings.urls`), add:

   ```python
   path("staff/floorplans/", include("floorplans.urls")),
   ```

   Ensure `path` and `include` are imported from `django.urls`.
4. Copy `manual_booking_floorplan.html` to `bookings/templates/bookings/manual_booking.html` (back up first).
5. Run `python manage.py makemigrations --check --dry-run floorplans`, `python manage.py migrate`, and `python manage.py check` with your normal environment activated.
6. Restart Gunicorn only after all checks succeed.

To open editor for hut ID 1: `/staff/floorplans/1/edit/` (replace 1 with actual hut ID). From the booking page, select a hut and dates, then click "Edit floor plan".

Security: staff auth and assigned-hut permissions on all endpoints, CSRF on writes, server-side collision/bounds validation, existing booking validation unchanged.

Limits: rectangular rooms on a 16×12 grid, 2–3 floors plus basement and floor 3. This is a room-location editor, not a wall/door architectural CAD tool. Positions are per room; adding rooms remains in Django admin.

**Important:** The migration in this package depends on `bookings.0001_initial`. If your project introduced the Room model in a later migration, adjust the dependency to that migration before running migrate. Confirm with `python manage.py showmigrations bookings`.
