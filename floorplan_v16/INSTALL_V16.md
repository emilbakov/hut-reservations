# V16 — Staff Reservation Details

Adds a hut-scoped reservation detail page and safe guest contact editing. No migrations. Dates, quantities, status, payments, and bed assignments remain managed by existing workflows.

## Install

```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_staff_reservations_v16.zip -d floorplan_v16
cp floorplan_v16/floorplans/staff_reservation.py floorplans/
cp floorplan_v16/floorplans/templates/floorplans/staff_reservation.html floorplans/templates/floorplans/
```

In `floorplans/urls.py`, add `from . import staff_reservation as sr16` and within `urlpatterns`:

```python
path('<int:hut_id>/reservations/<str:code>/', sr16.staff_reservation, name='staff_reservation'),
```

Run with production PostgreSQL settings:

```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a
source /etc/hut-reservations/postgres.env
set +a
python manage.py check
sudo systemctl restart gunicorn.service
```

Open `/staff/floorplans/3/reservations/<BOOKING_CODE>/` (replace hut ID and code).

To link calendar bars to V16, in `floorplans/templates/floorplans/staff_calendar.html`, replace the existing booking URL `{% url 'bookings:reservation' event.code %}` with `{% url 'floorplans:staff_reservation' hut.pk event.code %}`. V12 intercepts clicks to show a preview drawer; the drawer's 'Open reservation' link is assigned from the bar's `href`.

**Safety:** This view is staff-only and scoped to the hut. Reservations spanning multiple huts are intentionally rejected. Payment entries are read-only. Editing dates/bed counts should use existing booking services, because `modify_reservation` may remove physical-bed assignments when rebuilding reservation items. Back up and test on a staging database before production use.
