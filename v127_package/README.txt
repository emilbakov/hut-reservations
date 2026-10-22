SummitDesk guest reservation review dashboard (v127)
==================================================

Adds /staff/reservations/requests/ with pending/approved/declined public
requests, hut-scoped counts, search, room/bed/pricing/guest-note details,
and Approve / Decline actions using the existing secure v126 handler.

New manager emails link directly to the request review queue.
All reservations has a link to the new dashboard.

The existing v126 workflow retains its status transitions, manager access
checks, transactional row locking, bed holds, and guest notifications.
No migrations, schema changes, or data modification.

Install (from project root, after backup):
    unzip -o summitdesk_v127.zip
    python3 v127_package/install_v127.py
    python manage.py check
    python manage.py test bookings.test_approval_dashboard_v127 bookings.test_guest_approval_v126 bookings.test_reservation_management
    python manage.py test
    sudo systemctl restart gunicorn.service

Installer creates a timestamped backup under summitdesk_backups/.
Rollback script requires explicit path to that backup and refuses to
overwrite files changed after installation.

Notes: On production, source your venv and postgres.env before manage.py.
If tests fail, do not restart Gunicorn; restore with rollback script.
