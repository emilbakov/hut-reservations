SummitDesk v156 missing CSS repair

The v156 package omitted bookings/static/bookings/karlak_links_v155.css.
This repair adds the missing legacy stylesheet. v156 right-alignment CSS remains loaded after it and wins in the cascade.
No database migrations and no template changes.

Windows PowerShell:
scp "$env:USERPROFILE\Downloads\summitdesk_v156_missing_css_fix.zip" deploy@167.233.96.3:/home/deploy/
ssh deploy@167.233.96.3

Ubuntu Bash:
cd /home/deploy/hut-reservations
unzip -o /home/deploy/summitdesk_v156_missing_css_fix.zip
source myprojectenv/bin/activate
python manage.py test --settings=config.settings_test

After successful tests, collect static using production environment:
sudo bash -c '
set -a
source /etc/hut-reservations/postgres.env
set +a
cd /home/deploy/hut-reservations
runuser -u deploy -- myprojectenv/bin/python manage.py collectstatic --noinput
'

Then restart:
sudo systemctl restart gunicorn
sudo systemctl status gunicorn --no-pager
