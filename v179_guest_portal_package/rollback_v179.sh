#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test "$#" -eq 1 || { printf '%s\n' 'Usage: bash v179_guest_portal_package/rollback_v179.sh summitdesk_backups/guest_portal_v179_TIMESTAMP'; exit 2; }
TASK_PYTHON="$PWD/myprojectenv/bin/python"
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v179_guest_portal_package/rollback_v179.py "$1" --check
"$TASK_PYTHON" v179_guest_portal_package/rollback_v179.py "$1"
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'Previous booking source restored. Booking data retained.'
