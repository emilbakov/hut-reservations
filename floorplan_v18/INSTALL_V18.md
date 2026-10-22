# V18 — Drag to review room transfers

Requires V12 calendar, V17 reservation details, V6 bed management, and V8 physical bed assignments.

1. Back up your current `floorplans/templates/floorplans/staff_calendar.html`.
2. Copy `floorplans/staff_transfer.py` and both templates into their corresponding app paths.
3. Add `from . import staff_transfer as tr18` to `floorplans/urls.py`.
4. Add to existing urlpatterns:
   `path('<int:hut_id>/reservations/<str:code>/transfer/', tr18.review_transfer, name='review_transfer'),`
5. Set `DJANGO_SETTINGS_MODULE=config.settings_postgres` and load `/etc/hut-reservations/postgres.env` before running `python manage.py check`.
6. Restart Gunicorn, open `/staff/floorplans/3/calendar/`, and drag a booking bar onto a different room's name.

This is review-before-commit, not automatic transfer on drop. Single-room reservations only. The existing modify_reservation service validates inventory. Physical bed assignments must be removed first. No migrations.

CAUTION: This replaces the V12 calendar template and retains V12's navigation/layout. If you've customized that template since V12, merge the changes rather than blindly overwriting. Test in staging first.
