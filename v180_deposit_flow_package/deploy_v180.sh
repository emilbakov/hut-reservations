#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test -f manage.py
test -f /etc/hut-reservations/postgres.env
test -x myprojectenv/bin/python
TASK_PYTHON="$PWD/myprojectenv/bin/python"
TASK_PACKAGE="$PWD/v180_deposit_flow_package"
exec 9> .summitdesk_v180_deploy.lock
flock -n 9 || { printf '%s\n' 'Another v180 deployment or rollback is running.'; exit 1; }
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" "$TASK_PACKAGE/install_v180.py" --check
# No requests or old workers may write while the source and schema change.
sudo -v
sudo systemctl stop gunicorn.socket 2>/dev/null || true
sudo systemctl stop gunicorn.service
sudo systemctl stop summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer summitdesk-deposit-holds.service summitdesk-deposit-mail.service 2>/dev/null || true
trap 'sudo systemctl stop gunicorn.socket 2>/dev/null || true; sudo systemctl stop gunicorn.service; printf "%s\n" "v180 deployment stopped before completion. Gunicorn remains stopped. Fix the reported error and rerun this deployment; do not reverse the database migration." >&2' ERR
"$TASK_PYTHON" "$TASK_PACKAGE/install_v180.py" --apply
"$TASK_PYTHON" -c 'import hashlib, sys
from pathlib import Path
actual = hashlib.sha256(Path("bookings/test_reliability_v145.py").read_bytes()).hexdigest()
if actual != "036796cbedce91a884b933374e13b3aadc541d4f087b8cf983e3a0dce66ebf94":
    sys.exit("v180 replay repair is not installed; deployment stopped before tests.")
print("v180 replay repair verified: corrected /book/ fixture installed.")'
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
# Verify actual PostgreSQL row locks using a fresh synthetic database.
bash "$TASK_PACKAGE/verify_postgres_v180.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
for unit in summitdesk-deposit-holds.service summitdesk-deposit-holds.timer summitdesk-deposit-mail.service summitdesk-deposit-mail.timer; do
  sudo install -m 0644 "$TASK_PACKAGE/systemd/$unit" "/etc/systemd/system/$unit"
done
sudo systemctl daemon-reload
"$TASK_PYTHON" manage.py process_deposit_holds --dry-run
if systemctl cat gunicorn.socket >/dev/null 2>&1; then sudo systemctl start gunicorn.socket; fi
sudo systemctl start gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
sudo systemctl enable --now summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer
sudo systemctl is-active --quiet summitdesk-deposit-holds.timer summitdesk-deposit-mail.timer
trap - ERR
printf '%s\n' 'v180 deposit flow deployed. Hard refresh (Ctrl+F5).' 'Check hut payment instructions, approve a request, and verify the amount/deadline email. Existing confirmed bookings were not enrolled.' 'Deadline release and mail retry timers run separately every minute.'
