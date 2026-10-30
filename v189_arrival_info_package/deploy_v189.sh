#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v189_arrival_info_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
"$TASK_PYTHON" "$TASK_PACKAGE/install_v189.py" --check
"$TASK_PYTHON" "$TASK_PACKAGE/database_v189.py" --check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v189.py" --backup
"$TASK_PYTHON" "$TASK_PACKAGE/install_v189.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v189.py" --verify-installed
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v189.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'v189 arrival information deployed. Configure Settings > Arrival information, or edit the Hut in Django admin.' 'Unknown details remain blank. Existing rates, payments, galleries and queued emails were preserved.'
