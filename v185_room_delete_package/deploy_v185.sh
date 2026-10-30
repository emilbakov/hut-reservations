#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v185_room_delete_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
"$TASK_PYTHON" "$TASK_PACKAGE/install_v185.py" --check
"$TASK_PYTHON" "$TASK_PACKAGE/database_v185.py" --check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v185.py" --backup
"$TASK_PYTHON" "$TASK_PACKAGE/install_v185.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v185.py" --verify-installed
"$TASK_PYTHON" manage.py migrate --check --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v185.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'v185 admin room deletion deployed. Admin > Rooms > select unused rooms > Delete unused rooms and their beds.' 'No rooms, beds or reservations were deleted by deployment.'
