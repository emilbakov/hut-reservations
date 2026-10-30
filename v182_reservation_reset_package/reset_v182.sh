#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v182_reservation_reset_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
exec 9> .summitdesk_v180_deploy.lock
flock -n 9 || { printf '%s\n' 'A deployment, rollback or reset is already running.' >&2; exit 1; }
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
TASK_MODE="${1:---preview}"
case "$TASK_MODE" in
    --preview)
        [[ $# -le 1 ]] || exit 2
        exec "$TASK_PYTHON" "$TASK_PACKAGE/reset_reservations.py" --preview
        ;;
    --execute)
        [[ $# -eq 1 ]] || exit 2
        "$TASK_PYTHON" "$TASK_PACKAGE/reset_reservations.py" --preview
        ;;
    --restore)
        [[ $# -eq 2 ]] || { printf '%s\n' 'Usage: reset_v182.sh --restore BACKUP_DIRECTORY'; exit 2; }
        "$TASK_PYTHON" "$TASK_PACKAGE/reset_reservations.py" --check-restore "$2"
        printf '%s\n' 'Restoring the FULL database: changes since the backup will be replaced.'
        ;;
    *) printf '%s\n' 'Use --preview, --execute, or --restore BACKUP_DIRECTORY.' >&2; exit 2 ;;
esac
sudo -v
# Pause project jobs and cron while the application is offline. Restore only
# units which were active before this maintenance; do not enable anything.
TASK_UNIT_LIST=$(systemctl list-unit-files --type=service,timer,socket --no-legend --no-pager)
mapfile -t TASK_UNITS < <(printf '%s\n' "$TASK_UNIT_LIST" | awk '$1 ~ /^(gunicorn\.(socket|service)|summitdesk-.*\.(service|timer)|hut-reservations.*\.(service|timer)|cron\.service)$/ {print $1}' | sort -u)
TASK_ACTIVE=()
for TASK_UNIT in "${TASK_UNITS[@]}"; do
    if systemctl is-active --quiet "$TASK_UNIT"; then TASK_ACTIVE+=("$TASK_UNIT"); fi
done
TASK_STOPPED=0
resume_units() {
    local result=0 unit
    # Socket MUST precede service (v180 startup repair).
    for unit in gunicorn.socket gunicorn.service; do
        if printf '%s\n' "${TASK_ACTIVE[@]}" | grep -Fxq "$unit"; then sudo systemctl start "$unit" || result=1; fi
    done
    for unit in "${TASK_ACTIVE[@]}"; do
        case "$unit" in gunicorn.socket|gunicorn.service) continue;; esac
        sudo systemctl start "$unit" || result=1
    done
    return "$result"
}
finish() {
    local status=$?
    trap - EXIT INT TERM
    if [[ "$TASK_STOPPED" -eq 1 ]]; then
        if ! resume_units; then
            printf '%s\n' 'Maintenance ended, but one or more previously active services failed to restart. Check systemctl status.' >&2
            status=1
        fi
    fi
    exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
TASK_STOPPED=1
# Stop timers and cron before services. Stop socket before service.
for TASK_UNIT in "${TASK_ACTIVE[@]}"; do
    case "$TASK_UNIT" in *.timer|cron.service|gunicorn.socket) sudo systemctl stop "$TASK_UNIT";; esac
done
for TASK_UNIT in "${TASK_ACTIVE[@]}"; do
    case "$TASK_UNIT" in *.timer|cron.service|gunicorn.socket) continue;; esac
    sudo systemctl stop "$TASK_UNIT"
done
# Existing unmanaged manage.py/Gunicorn jobs must finish before a reset, too.
"$TASK_PYTHON" "$TASK_PACKAGE/check_workers.py"
if [[ "$TASK_MODE" == '--execute' ]]; then
    "$TASK_PYTHON" "$TASK_PACKAGE/reset_reservations.py" --execute --maintenance-stopped
else
    "$TASK_PYTHON" "$TASK_PACKAGE/reset_reservations.py" --restore "$2" --maintenance-stopped
fi
printf '%s\n' 'Maintenance command succeeded. Restarting the previously active services.'
