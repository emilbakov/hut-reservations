WEEKLY DRAG & DROP RESERVATION CALENDAR
Requires Availability Calendar and Interactive Calendar modules.

Back up your project and database first. Upload ZIP to Django project root:
  unzip -o drag_drop_calendar.zip
  python install_drag_drop_calendar.py
  python manage.py check
  python manage.py test bookings.test_calendar_drag
  python manage.py test bookings
  sudo systemctl restart gunicorn

Open /staff/availability/week/ or click the link in monthly availability calendar.

Drag a booking to a different date or room in the SAME hut. A separate confirmation
page appears; changes only happen after pressing Confirm move. The existing
modify_reservation service validates capacity and writes changes.

Limitations: single-room bookings only; preserves duration and bed count;
no automated email or refund; dragging does not work on touch-only devices,
but the existing edit form is available. Reservations that begin before the
visible week can be opened via the existing calendar instead.

SECURITY: CSRF protection on POST; staff login and hut scoping on all endpoints;
no cross-hut moves; service-side availability checks on submission.
