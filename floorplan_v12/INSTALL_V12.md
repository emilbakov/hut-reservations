# V12 — Interactive reservation workspace

Replace the existing V11 files only. Keep your V11 URL registration. No database migrations.

```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_reservation_workspace_v12.zip -d floorplan_v12
cp floorplans/staff_calendar.py floorplans/staff_calendar.py.backup.v11
cp floorplans/templates/floorplans/staff_calendar.html floorplans/templates/floorplans/staff_calendar.html.backup.v11
cp floorplan_v12/floorplans/staff_calendar.py floorplans/
cp floorplan_v12/floorplans/templates/floorplans/staff_calendar.html floorplans/templates/floorplans/
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
sudo systemctl restart gunicorn.service
```

Visit `/staff/floorplans/<hut_id>/calendar/`. New features: 7/14/28-day views, room/status/guest-code filters, and accessible click-to-preview reservation drawer. Filters only affect calendar, not today's KPIs. All modifications still use existing validated reservation pages. This release does not change the booking database.

Known limitations: calendar shows room-level reservations, not specific numbered bed assignments; maintenance closures are not drawn; all reservation bars remain read-only.
