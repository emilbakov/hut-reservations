# V15 — Staff reservation creation

Requires installed V14, bookings.forms.BookingForm, and bookings.services.create_reservation/free_beds. No migrations.

1. Backup existing floorplans/templates/floorplans/staff_overview.html.
2. Copy `floorplans/staff_new_booking.py` to your app.
3. Copy both templates into `floorplans/templates/floorplans/`.
4. In `floorplans/urls.py`, add `from . import staff_new_booking as nb15` and append `path("<int:hut_id>/new-booking/", nb15.staff_new_booking, name="staff_new_booking"),` to urlpatterns.
5. Run `python manage.py check` with `DJANGO_SETTINGS_MODULE=config.settings_postgres` and the PostgreSQL environment variables loaded; restart Gunicorn.
6. Visit `/staff/floorplans/<hut_id>/overview/` and use `+ New reservation`.

IMPORTANT: This uses the existing BookingForm and create_reservation service; it does not send guest confirmation emails automatically. It does not provide bed-number assignment; use V9 afterwards. Booking status follows BOOKING_INITIAL_STATUS. Test with a non-production reservation before operational use. If your service version is not the current one with maintenance closures, update that first.
