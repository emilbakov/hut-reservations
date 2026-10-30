#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test "$#" -eq 1 || { printf '%s\n' 'Usage: bash v169_hut_history_package/rollback_v169.sh summitdesk_backups/heritage_v169_TIMESTAMP'; exit 2; }
TASK_PYTHON="$PWD/myprojectenv/bin/python"
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v169_hut_history_package/rollback_v169.py "$1" --check
"$TASK_PYTHON" v169_hut_history_package/rollback_v169.py "$1"
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'Previous source restored. Booking data and additive reliability tables retained.'
