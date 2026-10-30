#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test "$#" -eq 1 || { printf '%s\n' 'Usage: bash v180_deposit_flow_package/rollback_v180.sh summitdesk_backups/deposit_flow_v180_TIMESTAMP'; exit 2; }
TASK_PYTHON="$PWD/myprojectenv/bin/python"
exec 9> .summitdesk_v180_deploy.lock
flock -n 9 || exit 1
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v180_deposit_flow_package/rollback_v180.py "$1" --check
sudo -v
sudo systemctl stop gunicorn.socket 2>/dev/null || true
sudo systemctl stop gunicorn.service
sudo systemctl stop summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer summitdesk-deposit-holds.service summitdesk-deposit-mail.service
# Repeat the database guard after stopping all writers.
"$TASK_PYTHON" manage.py check_deposit_rollback
"$TASK_PYTHON" v180_deposit_flow_package/rollback_v180.py "$1"
sudo systemctl disable summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl start gunicorn.service
if systemctl cat gunicorn.socket >/dev/null 2>&1; then sudo systemctl start gunicorn.socket; fi
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'Previous application source restored. Deposit history, payment ledger and additive database migration retained.'
