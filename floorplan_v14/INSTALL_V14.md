# V14 — Operations overview

Adds a read-only staff dashboard for the hut, inspired by property-management systems. Requires V11 calendar, V13 arrivals and V8 bed layout routes. No database migration.

1. Back up your app files and database as appropriate.
2. Copy `floorplans/staff_overview.py` into your application's `floorplans/` folder.
3. Copy `floorplans/templates/floorplans/staff_overview.html` into the matching templates folder.
4. In `floorplans/urls.py`, add `from . import staff_overview as ov14` and add `path('<int:hut_id>/overview/', ov14.staff_overview, name='staff_overview'),` to the existing `urlpatterns`.
5. Set `DJANGO_SETTINGS_MODULE=config.settings_postgres` and load `/etc/hut-reservations/postgres.env` before running `python manage.py check`.
6. Restart Gunicorn and open `/staff/floorplans/3/overview/` (replace 3 with your hut ID).

Metrics count room-level reservation quantities with status confirmed or pending. Check-out is exclusive. They do not represent actual check-ins or physical bed assignment availability; maintenance closures are not deducted. The upcoming arrivals panel shows at most 12 reservation items. The view is read-only.
