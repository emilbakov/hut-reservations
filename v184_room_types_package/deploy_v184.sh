#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v184_room_types_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
"$TASK_PYTHON" "$TASK_PACKAGE/install_v184.py" --check
"$TASK_PYTHON" "$TASK_PACKAGE/database_v184.py" --check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v184.py" --backup
"$TASK_PYTHON" "$TASK_PACKAGE/install_v184.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v184.py" --verify-installed
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v184.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'v184 Normal room and Studio types deployed. Set each unit type and actual extras from Edit type & extras in the staff calendar.' 'Both types keep exclusive whole-unit pricing. Guest-count preview uses a new script URL.'
