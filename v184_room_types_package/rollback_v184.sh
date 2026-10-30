#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v184_room_types_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
[[ $# -eq 1 ]] || { printf '%s\n' 'Pass the source backup directory printed during deployment.'; exit 2; }
"$TASK_PYTHON" "$TASK_PACKAGE/rollback_v184.py" --check "$1"
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/rollback_v184.py" "$1"
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'Previous source restored. Additive room-type migration and saved metadata retained. No reservation records removed.'
