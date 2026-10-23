SummitDesk v164 — Deposit information in Django admin

Files:
  bookings/admin.py
  bookings/test_deposit_admin_v164.py

What changes:
- Hut admin has an optional deposit policy inline (percentage, due days, reminders,
  grace period, auto-cancel toggle).
- Deposit policies have their own admin page.
- Reservation admin lists deposit due/remaining and shows a detailed read-only
  deposit summary plus read-only payment/refund ledger.
- No migrations or static collection are needed.
- Only superusers or authorized non-manager admin staff can access policy admin;
  hut managers remain blocked by the existing ProtectManagerAdmin policy.
- No payment entries are created or modified by this patch.

Ubuntu (already connected):
  cd /home/deploy/hut-reservations
  cp bookings/admin.py /home/deploy/admin.pre-v164.py
  unzip -o /home/deploy/summitdesk_v164_deposit_admin.zip
  myprojectenv/bin/python manage.py test bookings.test_deposit_admin_v164 --settings=config.settings_test
  myprojectenv/bin/python manage.py test --settings=config.settings_test
  sudo systemctl restart gunicorn

Run tests before restarting Gunicorn.
