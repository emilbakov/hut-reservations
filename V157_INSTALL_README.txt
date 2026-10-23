SUMMITDESK / KARLAK v157 — COMPACT LANGUAGE SELECTOR
======================================================
Install after v156 and the v156 missing CSS repair. No database migrations.

The language selector was taking the rightmost navbar slot and pushing links
inward. This patch places the smaller language selector before the nav links,
so links can sit at the far right. It affects the public headers only, not
staff sidebar, bookings, or footer layout.

1. PowerShell:
scp "$env:USERPROFILE\Downloads\summitdesk_v157_compact_language_nav.zip" deploy@167.233.96.3:/home/deploy/
ssh deploy@167.233.96.3

2. Ubuntu — backup and install:
cd /home/deploy
cp -a hut-reservations/bookings/templates/bookings/public_base_v124.html public_base_v124.pre-v157.html
cp -a hut-reservations/bookings/templates/bookings/base.html bookings_base.pre-v157.html
cd /home/deploy/hut-reservations
unzip -o /home/deploy/summitdesk_v157_compact_language_nav.zip

3. Test:
source myprojectenv/bin/activate
python manage.py test --settings=config.settings_test

4. Collect static files with production environment:
sudo bash -c '
set -a
source /etc/hut-reservations/postgres.env
set +a
cd /home/deploy/hut-reservations
runuser -u deploy -- myprojectenv/bin/python manage.py collectstatic --noinput
'

5. Restart only after successful tests and collectstatic:
sudo systemctl restart gunicorn
sudo systemctl status gunicorn --no-pager

6. Browser: Ctrl+Shift+R. Check public navbar at desktop and mobile sizes.
