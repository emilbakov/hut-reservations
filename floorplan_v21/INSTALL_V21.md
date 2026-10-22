# V21 — Housekeeping board

This adds a **manual** persistent cleaning checklist per physical numbered bed. It does not change reservation status, bed assignments, room capacity or BedClosure. Cleaning state is not date-specific; the selected date only filters occupancy/maintenance indicators. Beds start as "Not checked" until a manager marks them.

## Installation

1. Back up your PostgreSQL database and floorplans/models.py.
2. Copy `floorplans/housekeeping_models.py`, `floorplans/staff_housekeeping.py`, and `floorplans/templates/floorplans/staff_housekeeping.html` into the same locations in your project.
3. Append the following **single import line** at the END of `floorplans/models.py` (only once):

   `from .housekeeping_models import BedHousekeeping  # V21 model registration`

4. Add `from . import staff_housekeeping as hk21` to `floorplans/urls.py` and this entry inside its existing urlpatterns:

   `path('<int:hut_id>/housekeeping/', hk21.staff_housekeeping, name='staff_housekeeping'),`

5. IMPORTANT: run the following using the same PostgreSQL settings and env file as Gunicorn, **not SQLite**:

   ```bash
   cd /home/deploy/hut-reservations
   source myprojectenv/bin/activate
   export DJANGO_SETTINGS_MODULE=config.settings_postgres
   set -a; source /etc/hut-reservations/postgres.env; set +a
   python manage.py makemigrations floorplans
   python manage.py sqlmigrate floorplans <NEW_MIGRATION_NUMBER>  # optional inspection
   python manage.py migrate floorplans
   python manage.py check
   sudo systemctl restart gunicorn.service
   ```

6. Visit `/staff/floorplans/3/housekeeping/` (replace 3 with your hut ID).

## Safety notes
- Review the generated migration before applying; it should create `BedHousekeeping` only.
- No automated turnover cleaning: marking a bed "Ready" stays until manually changed. This is NOT a guarantee of availability.
- Maintenance closure and physical bed assignment remain managed by the existing V6/V9 workflows.
- Check-ins/check-outs do not automatically change cleaning state.
- The V21 screen is staff-only and scoped to hut managers/superusers via `permitted_hut`.
- Test on staging before using for real guests.
