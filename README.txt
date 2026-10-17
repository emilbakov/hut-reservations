GUEST COMMUNICATIONS — add-on for hut-reservations

Requires existing Deposit Deadlines module and payment management.

Installation (back up database first):
  cd /home/deploy/hut-reservations
  unzip -o guest_communications.zip
  python install_guest_communications.py
  python manage.py makemigrations bookings
  python manage.py migrate
  python manage.py check
  python manage.py test bookings
  sudo systemctl restart gunicorn

Dashboard: /staff/communications/

Preview (DEFAULT; no mail sent, no database changes):
  python manage.py send_guest_communications

Actually send:
  python manage.py send_guest_communications --send

Opt-in cancellation notices for cancelled reservations whose arrival is today
or later (does not send for historical cancellations):
  python manage.py send_guest_communications --send --include-cancellations

Sends pre-arrival emails two days before arrival, deposit-due emails on the due
date, and overdue-deposit emails once per due date. Duplicate prevention is
based on reservation, event type and event date. Failed sends are logged and
may be retried.

Existing booking confirmation emails use custom hut-specific templates when enabled;
otherwise the original confirmation email is unchanged. The legacy
send_deposit_reminders command also continues to work. DO NOT schedule both legacy deposit reminders and this
module's overdue deposit emails, or guests may receive duplicate messages.

Email delivery requires configured SMTP and DEFAULT_FROM_EMAIL.
This package never changes reservation status, payments, or refunds.
Run a manual preview and inspect results before enabling --send in cron.
