V13 — Arrivals & departures
===========================
Prerequisites: V12 and bookings.models.GuestStay with checked_in_at, checked_out_at, checked_in_by, checked_out_by. Check your model before installation. No migration required if GuestStay already exists and has been migrated.

1. Backup your existing project/database before deployment.
2. Copy floorplans/staff_arrivals.py to floorplans/staff_arrivals.py.
3. Copy both HTML files to floorplans/templates/floorplans/.
4. In floorplans/urls.py add:
   from . import staff_arrivals as ops13
   urlpatterns += [path('<int:hut_id>/arrivals/', ops13.staff_arrivals, name='staff_arrivals')]
   (If path is already imported, no new import is necessary.)
5. Optional: add a navigation link in staff_calendar.html:
   <a href="{% url 'floorplans:staff_arrivals' hut.pk %}">Arrivals & departures</a>
6. Use your production PostgreSQL settings and environment file:
   cd /home/deploy/hut-reservations
   source myprojectenv/bin/activate
   export DJANGO_SETTINGS_MODULE=config.settings_postgres
   set -a; source /etc/hut-reservations/postgres.env; set +a
   python manage.py check
   python manage.py showmigrations bookings
   sudo systemctl restart gunicorn.service
7. Open /staff/floorplans/<hut_id>/arrivals/

Important: This page records real GuestStay check-in/out events. It does not modify reservations, occupancy or assignments. Only staff permitted for the hut can access it. Only confirmed bookings can be checked in, within their reserved dates; checkout requires check-in. Daily counts are booked beds, not guest headcounts. Test with a non-production booking first.
