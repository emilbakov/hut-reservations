SummitDesk v165 — fix Django admin reservation save regression from v164.

Changes:
- bookings/admin.py: render payment history only for existing reservation GET pages,
  not on reservation add or POST (read-only inline must not require management form).
- bookings/test_deposit_admin_v165.py: tests add, change, and history visibility.

Install after v164. No migrations or collectstatic.
Test:
  myprojectenv/bin/python manage.py test bookings.tests.AdminTests bookings.test_deposit_admin_v164 bookings.test_deposit_admin_v165 --settings=config.settings_test
  myprojectenv/bin/python manage.py test --settings=config.settings_test
