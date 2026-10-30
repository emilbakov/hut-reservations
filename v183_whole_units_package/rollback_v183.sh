#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v183_whole_units_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
[[ $# -eq 1 ]] || { printf '%s\n' 'Pass the source backup directory printed during deployment.'; exit 2; }
"$TASK_PYTHON" "$TASK_PACKAGE/rollback_v183.py" --check "$1"
"$TASK_PYTHON" "$TASK_PACKAGE/database_v183.py" --rollback-check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v183.py" --rollback-check
"$TASK_PYTHON" "$TASK_PACKAGE/rollback_v183.py" "$1"
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'Previous source restored. Additive migration and its compatibility helper retained. No reservation records removed.'
