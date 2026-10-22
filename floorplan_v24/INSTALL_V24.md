# V24 — Hut-specific cleaning team permissions

Requires V23 installed. Back up your production PostgreSQL database before migrating.

1. Copy `floorplans/hut_staff.py` and `floorplans/staff_tasks.py` into the existing `floorplans/` app.
2. Copy both HTML files into `floorplans/templates/floorplans/` (back up existing `staff_tasks.html` first).
3. Append to `floorplans/models.py`: `from .hut_staff import HutCleaner` (retain all existing models/imports).
4. In `floorplans/urls.py`, retain the existing `staff_tasks` route and add:
   `from . import staff_tasks as team24` (if `staff_tasks` is already imported, use that module)
   `path('<int:hut_id>/cleaning-team/', team24.cleaner_team, name='cleaner_team'),`
5. Ensure the current `staff_tasks` URL points to `staff_tasks.staff_tasks` from this V24 file.
6. Run under production PostgreSQL settings and environment:
   `python manage.py makemigrations floorplans`
   `python manage.py sqlmigrate floorplans <new_migration_number>` (review SQL)
   `python manage.py migrate floorplans`
   `python manage.py check`
   `sudo systemctl restart gunicorn.service`
7. Open `/staff/floorplans/<hut_id>/cleaning-team/` as a manager. Add staff cleaners. Cleaners use `/staff/floorplans/<hut_id>/cleaning-tasks/`.

Security: Django `is_staff=True` is required for cleaners because this uses `staff_member_required`. This also permits Django admin login, though actual admin model access still depends on separate permissions. For cleaner-only accounts, review your admin permissions carefully. Only a hut manager or superuser may add/remove team members or edit any task. Cleaners can only view/update their own assigned tasks. Removing a cleaner prevents future access to that hut's task board; historical task assignments remain in the database.

No auto-task creation and no automatic change to bed cleaning readiness. Test in staging before production. The migration should add only the `HutCleaner` table.
