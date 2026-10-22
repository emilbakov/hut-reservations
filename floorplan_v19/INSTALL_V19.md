# V19 — Reservation Calendar Bed Availability Heatmap

Adds heatmap to V18 drag-transfer calendar. Replaces **two files only**: `floorplans/staff_calendar.py` and `floorplans/templates/floorplans/staff_calendar.html`. No new URL or migration.

## Deploy
1. Back up both existing files.
2. Copy the two files from this ZIP to the matching paths.
3. Set `DJANGO_SETTINGS_MODULE=config.settings_postgres` and load `/etc/hut-reservations/postgres.env` before `python manage.py check`.
4. Restart gunicorn and hard-refresh `/staff/floorplans/<hut_id>/calendar/`.

## Semantics
- `free = max(0, room.capacity - reserved quantities - distinct closed physical beds)` for each date; check-out date is excluded.
- Counts always include all pending and confirmed reservations, independent of calendar search/status filters.
- Closed bed IDs are deduplicated per night.
- Negative capacity is flagged red; free count stays at zero.
- **Important**: room-level unallocated reservations mean a particular numbered bed cannot be promised free based on the heatmap. A closure overlapping a booked/assigned bed may cause conservative double subtraction; investigate over-capacity flags.
- This is read-only; all V18 drag-transfer and reservation details links remain.

Test on staging first. No live integration tests have been performed.
