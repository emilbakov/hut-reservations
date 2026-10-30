#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test -f manage.py
test -f /etc/hut-reservations/postgres.env
test -x myprojectenv/bin/python
TASK_PYTHON="$PWD/myprojectenv/bin/python"
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v153_main_hut_package/install_v153.py --verify-installed
"$TASK_PYTHON" v153_main_hut_package/backup_database_v153.py
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" v153_main_hut_package/configure_main_hut_v153.py
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" manage.py collectstatic --noinput
media_root="$("$TASK_PYTHON" v153_main_hut_package/prepare_media_v153.py --root)"
if ! test -d "$media_root"; then
  sudo install -d -m 755 -o "$(id -un)" -g "$(id -gn)" -- "$media_root"
fi
test -w "$media_root"
"$TASK_PYTHON" v153_main_hut_package/prepare_media_v153.py
"$TASK_PYTHON" v153_main_hut_package/prepare_media_v153.py --nginx-snippet > v153_main_hut_package/nginx_media_generated.conf
sudo install -m 644 v153_main_hut_package/systemd/summitdesk-notification-retry-v145.service /etc/systemd/system/
sudo install -m 644 v153_main_hut_package/systemd/summitdesk-notification-retry-v145.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now summitdesk-notification-retry-v145.timer
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
sudo systemctl is-active --quiet summitdesk-notification-retry-v145.timer
printf '%s\n' 'v153 application deployed. Hard refresh (Ctrl+F5).' 'Main hut homepage and Карлък logo installed. Only the main hut accepts public requests. See MAIN_HUT.md and BRANDING.md.'
