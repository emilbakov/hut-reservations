SUMMITDESK v134 — GUEST COMMUNICATION (EMAIL + IN-APP)

Prerequisite: v133 installed. Back up Django project AND PostgreSQL database first.

1. Windows PowerShell (after downloading summitdesk_v134.zip to Downloads):
scp "$env:USERPROFILE\Downloads\summitdesk_v134.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

2. Ubuntu:
cd /home/deploy/hut-reservations
unzip -o summitdesk_v134.zip
python3 v134_package/install_v134.py

3. Targeted checks/tests (NO full suite):
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py migrate --noinput
python manage.py check
python manage.py test bookings.test_conversations_v134 bookings.test_communications bookings.test_self_service bookings.test_mobile_v133

Restart your EXISTING Django/Gunicorn service after tests pass.

STAFF URLS
/staff/communications/inbox/ — search reservations and open conversations
/staff/communications/quick-replies/ — create/edit per-hut quick replies
/staff/communications/ — existing automated email templates/history

GUEST URL
/guest/manage/<private-token>/ — conversation on existing reservation page

MANUAL EMAIL
Staff messages are saved to the guest's in-app conversation. The optional
"Send email copy" uses the existing Django email backend. Check production
SMTP settings before using it. "Email submitted" is not proof of delivery.
Guest messages are stored in-app, not emailed to managers. The staff inbox
must be checked manually. Incoming external email replies are NOT imported.
Messages do not change reservation status, inventory or payment.

SECURITY
- Staff restricted to assigned huts; token required for guest messages.
- CSRF on POST; 5 guest messages per hour per reservation.
- Guest link revocation disables posting and viewing.
- Safe placeholder whitelist and template escaping.
- Messages can be sent until 7 days after checkout.
- Backups stored under summitdesk_backups/communications_v134_*.

ROLLBACK SOURCE FILES (if needed, after taking database backup):
python3 v134_package/rollback_v134.py summitdesk_backups/communications_v134_TIMESTAMP
Rollback leaves database migration 0016 in place intentionally. A database
rollback needs a separate reviewed plan, especially if messages were sent.
