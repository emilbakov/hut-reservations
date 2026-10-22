#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test -f manage.py
test -f /etc/hut-reservations/postgres.env
test -x myprojectenv/bin/python
source myprojectenv/bin/activate
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
python v146_ui_ux_package/install_v146.py --check
python v146_ui_ux_package/backup_database_v146.py
python manage.py migrate --noinput
python manage.py check
python manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
python manage.py collectstatic --noinput
sudo install -m 644 v146_ui_ux_package/systemd/summitdesk-notification-retry-v145.service /etc/systemd/system/
sudo install -m 644 v146_ui_ux_package/systemd/summitdesk-notification-retry-v145.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now summitdesk-notification-retry-v145.timer
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
sudo systemctl is-active --quiet summitdesk-notification-retry-v145.timer
printf '%s\n' 'v146 deployment complete. Sign out and back in, then hard refresh the planner (Ctrl+F5).'
