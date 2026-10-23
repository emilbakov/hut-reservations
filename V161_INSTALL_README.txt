SummitDesk v161 — Floorplan arrivals/check-out PostgreSQL fix

Root cause candidate: SELECT FOR UPDATE with DISTINCT is not supported by PostgreSQL.
The arrivals POST handler previously used select_for_update().filter(items__room__hut=hut).distinct().
The patch keeps row locking and hut authorization but moves the item lookup to a subquery.

Files:
- floorplans/staff_arrivals.py
- floorplans/test_checkout_v161.py

No migrations, CSS, static changes, or settings changes.

Install:
cd /home/deploy/hut-reservations
cp floorplans/staff_arrivals.py /home/deploy/staff_arrivals.pre-v161.py
unzip -o /home/deploy/summitdesk_v161_checkout_postgres_fix.zip
source myprojectenv/bin/activate
python manage.py test floorplans.test_checkout_v161 --settings=config.settings_test
python manage.py test --settings=config.settings_test
sudo systemctl restart gunicorn

Do not use manage.py shell to test against production booking records.
