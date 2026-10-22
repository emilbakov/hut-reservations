# V33 — Hut-wide audit dashboard

Requires V31/V32 audit history and V28 SummitDesk navigation. No database migration.

## Installation

```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_audit_dashboard_v33.zip -d floorplan_v33
cp floorplan_v33/floorplans/staff_audit_dashboard.py floorplans/
cp floorplan_v33/floorplans/templates/floorplans/staff_audit_dashboard.html floorplans/templates/floorplans/
```

Add in `floorplans/urls.py`:

```python
from . import staff_audit_dashboard as audit33
```

Within `urlpatterns`, add:

```python
path('<int:hut_id>/audit/', audit33.staff_audit_dashboard, name='staff_audit_dashboard'),
```

Run production checks:

```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
sudo systemctl restart gunicorn.service
```

Open `/staff/floorplans/3/audit/` (replace 3 with your hut ID).

## Verification

1. Log in as a hut manager: verify the dashboard and filtered CSV export.
2. Log in as a cleaner: verify HTTP 403.
3. Try another hut ID: verify you cannot access it without manager rights.
4. Compare counts with V32 reservation history.

CSV export is limited to 10,000 newest matching rows and escapes formula-like text. The export may contain operational details, so handle downloaded files appropriately. Counts by staff represent events, not employee productivity or performance.

No existing files are overwritten by the package. The URL registration is a manual addition. No live-server integration test has been performed.
