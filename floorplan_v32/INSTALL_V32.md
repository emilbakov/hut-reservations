# SummitDesk V32 — actor-aware reservation audit

Prerequisite: V31 installed and its signal registration working. V32 replaces V31 audit modules and adds request-scoped actor middleware. Back up PostgreSQL and files first.

## Copy
```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_audit_v32.zip -d floorplan_v32
mkdir -p backups_v32
cp floorplans/reservation_history.py floorplans/reservation_audit.py floorplans/staff_history.py backups_v32/
cp floorplans/templates/floorplans/staff_history.html backups_v32/
cp floorplan_v32/floorplans/{reservation_history.py,reservation_audit.py,staff_history.py,audit_actor.py} floorplans/
cp floorplan_v32/floorplans/templates/floorplans/staff_history.html floorplans/templates/floorplans/
```

## Enable actor attribution
In your production Django settings, add `floorplans.audit_actor.ReservationAuditActorMiddleware` to `MIDDLEWARE` **after** `django.contrib.auth.middleware.AuthenticationMiddleware` (not before). Do not remove existing middleware.

## Migration
V31 `ReservationHistoryEvent` already exists and is imported from `floorplans/models.py`. V32 adds a JSONField `changes` with a default. Load production settings and review migration before applying:
```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py makemigrations floorplans
python manage.py sqlmigrate floorplans <NEW_MIGRATION_NUMBER>
python manage.py migrate floorplans
python manage.py check
sudo systemctl restart gunicorn.service
```
Expected schema change: only `ReservationHistoryEvent.changes` JSONField. If migration proposes other unrelated changes, stop and inspect.

## Test
Open `/staff/floorplans/3/reservations/BOOKINGCODE/history/`, edit a non-sensitive reservation field through the staff UI, and verify actor + before/after values. Check cancellation and room transfers. Filter by type, actor, date. Check unauthorized cleaner receives 403.

## Limitations
- V32 does not backfill earlier changes or actors.
- Signals capture normal `.save()` operations, not `QuerySet.update()`, `bulk_update()`, raw SQL, or all many-to-many changes.
- Actor is available for synchronous saves during authenticated HTTP requests. Background tasks and other processes show system/unknown.
- Guest name, email, phone, and notes are redacted in structured diffs. Existing V31 text remains as originally recorded.
- Actor attribution uses the authenticated request user; it is not cryptographic proof of who performed a change.
- If a reservation spans multiple huts, the history view remains inaccessible as in V31.
