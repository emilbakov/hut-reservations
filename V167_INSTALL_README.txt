SUMMITDESK v167 — ADMIN CANCELLATION + DEPOSIT SETTLEMENT

Adds a one-reservation-at-a-time cancellation flow in Django Admin:
Reservations -> select one -> Action: Cancel and handle deposit; or open a reservation
and click "Cancel / handle deposit" in its Deposit information section.

Decisions: no funds, retain received funds, or record a previously completed full/
partial refund. Cancellation releases beds and preserves reservation/payment records.
A read-only Cancellation settlements admin list records the decision and amounts.

IMPORTANT: Recording a refund does NOT send money. Refund externally first, then
confirm in the form. Only one settlement record is permitted per reservation.
Existing staff payments workflow can record later refunds; the settlement is a
snapshot at the time of cancellation, not a live running balance.

Install (Ubuntu, from /home/deploy/hut-reservations):
  unzip -o /home/deploy/summitdesk_v167_cancellation_deposit_workflow.zip
  myprojectenv/bin/python manage.py test bookings.test_cancellation_deposit_v167 --settings=config.settings_test
  myprojectenv/bin/python manage.py test --settings=config.settings_test

Apply migration with production env AFTER successful tests:
  sudo bash -c '
  set -a
  source /etc/hut-reservations/postgres.env
  set +a
  cd /home/deploy/hut-reservations
  runuser -u deploy -- myprojectenv/bin/python manage.py migrate --noinput
  '

Then: sudo systemctl restart gunicorn
No collectstatic required; template and Python changes only.
