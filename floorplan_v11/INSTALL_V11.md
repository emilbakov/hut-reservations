# V11 — SummitDesk staff calendar

This is an additive, read-only staff dashboard. It does not change models, migrations, reservation status, bed assignments, or public booking pages.

1. Copy `floorplans/staff_calendar.py` into the live `floorplans/` directory.
2. Copy `floorplans/templates/floorplans/staff_calendar.html` into the live templates directory.
3. In `floorplans/urls.py` add `from . import staff_calendar as sc11` and inside the existing `urlpatterns` add:

   `path("<int:hut_id>/calendar/", sc11.staff_calendar, name="staff_calendar"),`

4. With your PostgreSQL environment loaded, run `python manage.py check`, restart Gunicorn, and open `/staff/floorplans/<hut_id>/calendar/`.

Important: existing routes named `floorplans:visual_beds`, `floorplans:bed_layout`, `floorplans:availability_map`, and `bookings:dashboard` are used in the template. If your route names differ, adjust these links first. No database migrations needed.

Security: this uses the existing `permitted_hut` check and staff-only decorator. The timeline only includes pending and confirmed reservations, excludes cancelled reservations, and uses checkout-exclusive dates. Occupancy is reserved bed quantity (not physical bed allocation) and does not subtract maintenance closures. Pending/arrival/departure summary metrics count reserved beds, not distinct guests or bookings.
