# V23 — Staff housekeeping task board

Prerequisite: V21 and V22 installed. Take a production PostgreSQL backup before migrations.

1. Copy `floorplans/housekeeping_tasks.py`, `floorplans/staff_tasks.py`, and `floorplans/templates/floorplans/staff_tasks.html` into the matching project paths.
2. Append to the end of `floorplans/models.py` (keep V21 and V22 imports):
   `from .housekeeping_tasks import HousekeepingTask`
3. Add to `floorplans/urls.py`:
   `from . import staff_tasks as tasks23`
   and inside urlpatterns:
   `path('<int:hut_id>/cleaning-tasks/', tasks23.staff_tasks, name='staff_tasks'),`
4. Load production environment before management commands:
   ```bash
   cd /home/deploy/hut-reservations
   source myprojectenv/bin/activate
   export DJANGO_SETTINGS_MODULE=config.settings_postgres
   set -a; source /etc/hut-reservations/postgres.env; set +a
   python manage.py makemigrations floorplans
   python manage.py sqlmigrate floorplans <NEW_MIGRATION_NUMBER>  # optional review
   python manage.py migrate floorplans
   python manage.py check
   sudo systemctl restart gunicorn.service
   ```
5. Open `/staff/floorplans/3/cleaning-tasks/` (change hut ID).

Notes:
- Assignable staff currently includes all active Django staff accounts, not just hut-specific personnel. Add a hut-staff relationship if staff assignments must be hut-restricted.
- Task completion does not change `BedHousekeeping` cleaning readiness, maintenance closure, or booking availability.
- Tasks are manually created, one per bed per date. V22 checkout cleaning does not auto-create V23 tasks.
- No live production integration tests have been performed. Test on staging before rollout.
