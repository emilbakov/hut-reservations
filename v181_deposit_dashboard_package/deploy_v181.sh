#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
TASK_PYTHON="$PWD/myprojectenv/bin/python"
TASK_PACKAGE="$PWD/v181_deposit_dashboard_package"
exec 9> .summitdesk_v180_deploy.lock
flock -n 9 || { printf '%s\n' 'Another deployment or rollback is running.'; exit 1; }
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" "$TASK_PACKAGE/install_v181.py" --check
"$TASK_PYTHON" manage.py migrate --check
systemctl cat summitdesk-deposit-holds.timer >/dev/null
systemctl cat summitdesk-deposit-mail.timer >/dev/null
sudo -v
sudo systemctl stop gunicorn.socket 2>/dev/null || true
sudo systemctl stop gunicorn.service
sudo systemctl stop summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer summitdesk-deposit-holds.service summitdesk-deposit-mail.service
trap 'sudo systemctl stop gunicorn.socket 2>/dev/null || true; sudo systemctl stop gunicorn.service; printf "%s\n" "v181 stopped before completion. Fix the reported error and rerun deploy_v181.sh. No new migration was applied." >&2' ERR
"$TASK_PYTHON" "$TASK_PACKAGE/install_v181.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v181.py" --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v181.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
if systemctl cat gunicorn.socket >/dev/null 2>&1; then sudo systemctl start gunicorn.socket; fi
sudo systemctl start gunicorn.service
sudo systemctl enable --now summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer
sudo systemctl is-active --quiet gunicorn.service summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer
trap - ERR
printf '%s\n' 'v181 Deposits dashboard deployed. Hard refresh (Ctrl+F5) and open /staff/deposits/.' 'Replay test correction and socket-first startup are included. No new database migration.'
