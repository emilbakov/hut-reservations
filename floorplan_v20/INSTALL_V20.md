# V20 — Expandable numbered-bed calendar

Requires V19 and V8 Bed model / permanent bed identity. Replaces V19 calendar view and template only. No migrations or URL changes.

1. Back up floorplans/staff_calendar.py and floorplans/templates/floorplans/staff_calendar.html.
2. Copy the two files from this ZIP to the matching paths.
3. Use DJANGO_SETTINGS_MODULE=config.settings_postgres and load /etc/hut-reservations/postgres.env before `python manage.py check`.
4. Restart Gunicorn, open /staff/floorplans/<hut_id>/calendar/, click Show numbered beds.

Grey: unassigned (NOT guaranteed free); green: explicitly assigned; purple: maintenance closure; red: conflicting assignment/closure. Only active pending/confirmed bookings are shown. No write actions added. Existing V18 transfer review remains in the template.

IMPORTANT: This is a read-only view of numbered-bed assignment state, not an independent inventory availability calculator. Back up and test on staging before deploying.
