#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test "$#" -eq 1 || { printf '%s\n' 'Usage: bash v181_deposit_dashboard_package/rollback_v181.sh summitdesk_backups/deposit_dashboard_v181_TIMESTAMP'; exit 2; }
TASK_PYTHON="$PWD/myprojectenv/bin/python"
exec 9> .summitdesk_v180_deploy.lock
flock -n 9 || exit 1
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v181_deposit_dashboard_package/rollback_v181.py "$1" --check
sudo -v
sudo systemctl stop gunicorn.socket 2>/dev/null || true
sudo systemctl stop gunicorn.service
sudo systemctl stop summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer summitdesk-deposit-holds.service summitdesk-deposit-mail.service
"$TASK_PYTHON" v181_deposit_dashboard_package/rollback_v181.py "$1"
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
if systemctl cat gunicorn.socket >/dev/null 2>&1; then sudo systemctl start gunicorn.socket; fi
sudo systemctl start gunicorn.service
sudo systemctl enable --now summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer
sudo systemctl is-active --quiet gunicorn.service summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer
printf '%s\n' 'Previous v180 dashboard source restored. Deposit flow, jobs and payment records retained.'
