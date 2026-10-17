INTERACTIVE AVAILABILITY CALENDAR (staff only)

Prerequisite: existing Availability Calendar module, 171 passing tests.

1. Back up the database and project files.
2. Upload interactive_calendar.zip to /home/deploy/hut-reservations
3. cd /home/deploy/hut-reservations
4. unzip -o interactive_calendar.zip
5. python install_interactive_calendar.py
6. python manage.py check
7. python manage.py test bookings.test_calendar_actions
8. python manage.py test bookings
9. Only if passing: sudo systemctl restart gunicorn

No migrations needed. Expected total: 179 tests.

URLs:
 /staff/availability/ (existing calendar)
 /staff/availability/new/ (create booking)
 /staff/availability/edit/<code>/ (edit dates and beds)

Capacity is rechecked using existing create_reservation/modify_reservation
with room locks; hut manager permissions are enforced. Only single-room
bookings can be edited from this screen. For multi-room bookings use the
existing manager reservation tools. Edits do not modify guest identity.

Creating bookings from this staff screen does not automatically send
confirmation email, collect payment, or change deposit settings. Review
those separately using existing manager workflows.
