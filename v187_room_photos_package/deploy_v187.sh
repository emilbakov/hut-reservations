#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v187_room_photos_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
"$TASK_PYTHON" "$TASK_PACKAGE/install_v187.py" --check
"$TASK_PYTHON" "$TASK_PACKAGE/database_v187.py" --check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v187.py" --backup
"$TASK_PYTHON" "$TASK_PACKAGE/install_v187.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v187.py" --verify-installed
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v187.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'v187 optional room photos deployed. Photos are blank until uploaded under Admin > Rooms or Edit type & extras.' 'Photos appear only in booking options. Homepage, seasonal rates and existing reservations are unchanged.'
