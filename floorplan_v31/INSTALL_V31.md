# SummitDesk V31 — Reservation activity timeline

## Overview
- New append-only `ReservationHistoryEvent` model and manager-only reservation timeline.
- Automatic future event recording for reservation field changes, cancellation, room allocations and transfers, and check-in/out if the installed GuestStay model uses `checked_in_at` and `checked_out_at`.
- Actor is intentionally unknown for automatic signals; no false attribution.
- No historical backfill: changes before installation are not available.
- V30 required.

## Copy files
From `/home/deploy/hut-reservations`:

```bash
unzip -o floorplan_activity_v31.zip -d floorplan_v31
cp floorplans/models.py floorplans/models.py.backup.v30
cp floorplans/urls.py floorplans/urls.py.backup.v30
cp floorplan_v31/floorplans/reservation_history.py floorplans/
cp floorplan_v31/floorplans/reservation_audit.py floorplans/
cp floorplan_v31/floorplans/reservation_audit_apps.py floorplans/
cp floorplan_v31/floorplans/staff_history.py floorplans/
cp floorplan_v31/floorplans/templates/floorplans/staff_history.html floorplans/templates/floorplans/
```

## Model registration
Append to `floorplans/models.py`:
```python
from .reservation_history import ReservationHistoryEvent
```

## Signals registration
Inspect `floorplans/apps.py` if present. Do **not** replace an existing AppConfig containing other `ready()` logic.

Preferred if no custom app config exists: in production `INSTALLED_APPS`, replace the `floorplans` entry with:
```python
'floorplans.reservation_audit_apps.FloorplansV31Config',
```

If an existing `FloorplansConfig` is already in use, add to its `ready()` method (preserving its existing code):
```python
from . import reservation_audit
reservation_audit.register_optional_signals()
```

The signal module must be imported at application startup; importing it only from a view is insufficient.

## URL
Add to `floorplans/urls.py`:
```python
from . import staff_history as history31
```
And within `urlpatterns`:
```python
path('<int:hut_id>/reservations/<str:code>/history/', history31.staff_history, name='staff_history'),
```

## Migrations and restart
Backup production PostgreSQL first, then:
```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py makemigrations floorplans
# Review generated migration: it should create ReservationHistoryEvent only.
python manage.py migrate floorplans
python manage.py check
sudo systemctl restart gunicorn.service
```

Open `/staff/floorplans/3/reservations/BOOKINGCODE/history/` with a real reservation code. For a clickable link on V16 reservation details, add:
```django
<a href="{% url 'floorplans:staff_history' hut.pk reservation.code %}">Activity history</a>
```

## Limitations
- Signals only capture Django ORM `.save()` and `.delete()` operations; `QuerySet.update()`, `bulk_update()` and raw SQL bypass them.
- No reliable user attribution for automatic events.
- If your GuestStay fields differ, check-in/out signals will not attach until adapted.
- A booking created before a room item exists receives its first event when an item is added.
- V31 records changes from deployment onward, not past history.
- Test on staging before production; live integration has not been verified.
