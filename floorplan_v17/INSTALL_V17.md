# V17 Staff Reservation Editing

Requires V16 and existing bookings.services.modify_reservation.

Back up your PostgreSQL database and V16 files. Copy staff_reservation.py and staff_reservation.html into the matching floorplans paths. No new URLs or migrations.

Important: the existing modify_reservation service deletes/recreates ReservationItems, which would cascade physical bed assignments. This UI blocks edits when any BedAssignment exists; unassign beds in V9 first. Verify your installed services.py matches this behavior before deployment.

Run Django checks with DJANGO_SETTINGS_MODULE=config.settings_postgres and variables loaded from /etc/hut-reservations/postgres.env. Test on staging first.
