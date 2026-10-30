#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v185_room_delete_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
[[ $# -eq 1 ]] || { printf '%s\n' 'Pass the source backup directory printed during deployment.'; exit 2; }
"$TASK_PYTHON" "$TASK_PACKAGE/rollback_v185.py" --check "$1"
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/rollback_v185.py" "$1"
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'Previous source restored. No database changes were reversed. Rooms previously deleted through admin are not restored by source rollback.'
