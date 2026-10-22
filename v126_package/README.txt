SummitDesk v126 — Guest booking requests awaiting manager approval

Public guest submissions now create PENDING requests, not confirmed bookings.
Requests hold the chosen beds until approved or cancelled by a manager.
The existing short-lived payment-hold expiry continues to apply to other pending
reservations, but never to guest approval requests.

The guest sees an awaiting-approval screen and gets a request-received email.
Assigned hut managers (and the configured notification address) are notified.
A manager can Approve or Decline from /staff/reservations/.
Approval sends the existing confirmation email. Decline sends a decline email.

Requires public hut page v125. Includes a database migration (bookings 0013).
Back up PostgreSQL before installing. This patch does not retroactively change
existing reservations. SMTP must be configured for emails to be delivered.

From the project root:
  unzip -o summitdesk_v126.zip
  python3 v126_package/install_v126.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  python manage.py migrate bookings
  python manage.py test bookings.test_guest_approval_v126
  sudo systemctl restart gunicorn.service

Rollback BEFORE the database migration only:
  python3 v126_package/rollback_v126.py summitdesk_backups/guest_approval_TIMESTAMP
This script refuses to run after migration 0013 is applied. Once live guest
requests exist, reversing only the files can cause automatic cancellations.
Coordinate a full database-safe rollback instead.

No changes to staff-created reservation defaults or public URLs.
