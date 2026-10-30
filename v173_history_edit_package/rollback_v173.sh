#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test "$#" -eq 1 || { printf '%s\n' 'Usage: bash v173_history_edit_package/rollback_v173.sh summitdesk_backups/history_edit_v173_TIMESTAMP'; exit 2; }
TASK_PYTHON="$PWD/myprojectenv/bin/python"
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v173_history_edit_package/rollback_v173.py "$1" --check
"$TASK_PYTHON" v173_history_edit_package/rollback_v173.py "$1"
"$TASK_PYTHON" manage.py check
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'Previous history template and translations restored. Booking data retained.'
