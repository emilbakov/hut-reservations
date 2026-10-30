#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v183_1_whole_units_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
"$TASK_PYTHON" "$TASK_PACKAGE/install_v183.py" --check
"$TASK_PYTHON" "$TASK_PACKAGE/database_v183.py" --check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v183.py" --backup
"$TASK_PYTHON" "$TASK_PACKAGE/install_v183.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v183.py" --verify-installed
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v183.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'v183 whole-room, studio and apartment booking deployed. Hard refresh /book/ and staff booking screens.' 'Saved nightly prices now apply to the whole unit. Guest count does not multiply the price. Existing reservation totals were preserved.'
