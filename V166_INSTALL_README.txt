SummitDesk v166 — Standalone Deposits in Django Admin
=======================================================

What changes:
- Admin > Bookings > Deposits: separate read-only deposit transaction list.
- Shows amount, reservation link, guest, hut, method, date, staff member and note.
- Search by reservation code, guest name/email or note; filter by method/date.
- Only actual deposit ledger transactions are shown (not normal payments/refunds).
- No ledger duplication, no financial changes, no relaxation of PROTECT on reservation deletion.
- New proxy model requires a state-only migration; it creates NO database table.
- Existing admin and staff payment recording flows remain unchanged.

Install:
cd /home/deploy/hut-reservations
cp bookings/admin.py /home/deploy/admin.pre-v166.py
cp bookings/models.py /home/deploy/models.pre-v166.py
unzip -o /home/deploy/summitdesk_v166_standalone_deposits.zip
myprojectenv/bin/python manage.py test bookings.test_deposit_admin_v166 --settings=config.settings_test
myprojectenv/bin/python manage.py test --settings=config.settings_test

After successful tests, migrate using production environment:
sudo bash -c '
set -a
source /etc/hut-reservations/postgres.env
set +a
cd /home/deploy/hut-reservations
runuser -u deploy -- myprojectenv/bin/python manage.py migrate --noinput
'

sudo systemctl restart gunicorn

No collectstatic needed.
