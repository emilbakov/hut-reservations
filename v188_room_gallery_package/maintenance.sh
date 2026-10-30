# Sourced only after the caller has set TASK_PACKAGE and TASK_PYTHON.
exec 9> .summitdesk_v180_deploy.lock
flock -n 9 || { printf '%s\n' 'Another deployment, rollback or reset is running.' >&2; exit 1; }
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
TASK_STATE="$TASK_PACKAGE/maintenance_units.txt"
stop_writers() {
 sudo -v
 if [[ ! -e "$TASK_STATE" ]]; then
  local inventory unit
  inventory=$(systemctl list-unit-files --type=service,timer,socket --no-legend --no-pager)
  : > "$TASK_STATE"
  chmod 600 "$TASK_STATE"
  while read -r unit; do
   if systemctl is-active --quiet "$unit"; then printf '%s\n' "$unit" >> "$TASK_STATE"; fi
  done < <(printf '%s\n' "$inventory" | awk '$1 ~ /^(gunicorn\.(socket|service)|summitdesk-.*\.(service|timer)|hut-reservations.*\.(service|timer)|cron\.service)$/ {print $1}' | sort -u)
 fi
 mapfile -t TASK_ACTIVE < "$TASK_STATE"
 for TASK_UNIT in "${TASK_ACTIVE[@]}"; do
  [[ "$TASK_UNIT" =~ ^(gunicorn\.(socket|service)|summitdesk-.*\.(service|timer)|hut-reservations.*\.(service|timer)|cron\.service)$ ]] || { printf '%s\n' 'Unexpected maintenance unit name.' >&2; exit 1; }
 done
 trap maintenance_failure ERR
 for TASK_UNIT in "${TASK_ACTIVE[@]}"; do
  case "$TASK_UNIT" in *.timer|cron.service|gunicorn.socket) sudo systemctl stop "$TASK_UNIT";; esac
 done
 for TASK_UNIT in "${TASK_ACTIVE[@]}"; do
  case "$TASK_UNIT" in *.timer|cron.service|gunicorn.socket) continue;; esac
  sudo systemctl stop "$TASK_UNIT"
 done
 "$TASK_PYTHON" "$TASK_PACKAGE/check_workers.py"
}
resume_writers() {
 for TASK_UNIT in gunicorn.socket gunicorn.service; do
  if grep -Fxq "$TASK_UNIT" "$TASK_STATE"; then sudo systemctl start "$TASK_UNIT"; fi
 done
 for TASK_UNIT in "${TASK_ACTIVE[@]}"; do
  case "$TASK_UNIT" in gunicorn.socket|gunicorn.service) continue;; esac
  sudo systemctl start "$TASK_UNIT"
 done
 rm "$TASK_STATE"
 trap - ERR
}

maintenance_failure() {
 local status=$? unit
 trap - ERR
 sudo systemctl stop gunicorn.socket 2>/dev/null || true
 sudo systemctl stop gunicorn.service 2>/dev/null || true
 for unit in "${TASK_ACTIVE[@]}"; do sudo systemctl stop "$unit" 2>/dev/null || true; done
 printf '%s\n' 'v188 maintenance stopped before completion. Fix the reported error and rerun this wrapper. Services were left stopped. Do not reverse migration 0033.' >&2
 exit "$status"
}
