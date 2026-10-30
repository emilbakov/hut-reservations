#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test "$#" -eq 1 || { printf '%s\n' 'Usage: bash v153_main_hut_package/rollback_v153.sh summitdesk_backups/main_hut_v153_TIMESTAMP'; exit 2; }
TASK_PYTHON="$PWD/myprojectenv/bin/python"
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v153_main_hut_package/rollback_v153.py "$1" --check
sudo systemctl disable --now summitdesk-notification-retry-v145.timer 2>/dev/null || true
"$TASK_PYTHON" v153_main_hut_package/rollback_v153.py "$1"
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
if test -f bookings/notifications_v145.py; then
  sudo systemctl enable --now summitdesk-notification-retry-v145.timer
fi
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'Previous source restored. Booking data and additive reliability tables retained.'
