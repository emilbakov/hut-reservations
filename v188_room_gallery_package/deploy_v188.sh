#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v188_room_gallery_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
"$TASK_PYTHON" "$TASK_PACKAGE/install_v188.py" --check
"$TASK_PYTHON" "$TASK_PACKAGE/database_v188.py" --check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v188.py" --backup
"$TASK_PYTHON" "$TASK_PACKAGE/install_v188.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v188.py" --verify-installed
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v188.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'v188 room photo galleries deployed. Add additional photos from Admin > Rooms or Edit type & extras.' 'Existing main photos stay first. Galleries are optional, booking options only, and start empty.'
