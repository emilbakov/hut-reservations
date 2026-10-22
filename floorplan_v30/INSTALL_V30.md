# SummitDesk V30 — Unified reservation search, breadcrumbs, active navigation

## Requirements
V28 and V29 installed. Existing `floorplans:staff_reservation` route accepts `(hut_id, code)`. The existing V24 `floorplans.staff_tasks.access` helper enforces hut membership.

## Install
Upload ZIP from Windows:
```powershell
scp "$HOME\Downloads\floorplan_workspace_v30.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```
On server:
```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_workspace_v30.zip -d floorplan_v30
mkdir -p backups_v30
cp floorplans/templatetags/summitdesk_nav.py backups_v30/
cp floorplans/templates/floorplans/includes/summitdesk_nav.html backups_v30/
cp floorplans/urls.py backups_v30/urls.py
cp floorplan_v30/floorplans/templatetags/summitdesk_nav.py floorplans/templatetags/
cp floorplan_v30/floorplans/templates/floorplans/includes/summitdesk_nav.html floorplans/templates/floorplans/includes/
cp floorplan_v30/floorplans/staff_search.py floorplans/
cp floorplan_v30/floorplans/templates/floorplans/staff_search.html floorplans/templates/floorplans/
```
In `floorplans/urls.py` add:
```python
from . import staff_search as search30
```
Inside `urlpatterns` add:
```python
path('<int:hut_id>/search/', search30.staff_search, name='staff_search'),
```
Then:
```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
sudo systemctl restart gunicorn.service
```
No migrations. Visit `/staff/floorplans/3/search/?q=guest` (replace 3 with your hut ID).

## Security and behavior
- Search is GET-only, login-required, and manager-only. It filters ReservationItem by the authorized hut **before** searching reservation fields; cross-hut reservations cannot be found through this view.
- Queries are limited to 100 characters, results to 50 unique reservations, and status is allowlisted.
- Existing pages retain their original templates and logic; only shared navigation tag/template are replaced.
- Cleaner navigation has no search control, and the search endpoint denies cleaner access.
- Test manager vs cleaner accounts, active highlighting on detail/edit/transfer, mobile header, and existing booking flows.

## Rollback
Restore the two backed-up nav files and `floorplans/urls.py` from `backups_v30/`, then restart Gunicorn. Search files can remain unused.

## Limitations
No live server integration test. Nested reservation routes not in the active route set may need their names added to `RESERVATION_ROUTES`. Django `request` template context processor must be enabled. Search results are limited to the first 251 matching room-items before deduplication; a booking with many room-items could reduce distinct result count.
