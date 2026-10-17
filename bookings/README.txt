Financial Dashboard & CSV Reports
================================
Requires the previously installed Payment Management feature.

1. Back up your production database.
2. Upload and unzip this package in /home/deploy/hut-reservations
3. python install_financial_reports.py
4. python manage.py check
5. python manage.py test bookings
6. If tests pass: sudo systemctl restart gunicorn

Visit /staff/finances/

Cash movements are grouped by transaction creation month.
Outstanding balances are CURRENT snapshots of active reservations arriving in
the selected month. Refunds reduce net receipts. Deposits are included in receipts.
Cancelled reservations do not contribute to outstanding balances.
No migrations needed.
