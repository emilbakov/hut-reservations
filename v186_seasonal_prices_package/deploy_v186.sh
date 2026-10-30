#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd /home/deploy/hut-reservations
TASK_PACKAGE="$PWD/v186_seasonal_prices_package"
TASK_PYTHON="$PWD/myprojectenv/bin/python"
source "$TASK_PACKAGE/maintenance.sh"
"$TASK_PYTHON" "$TASK_PACKAGE/install_v186.py" --check
"$TASK_PYTHON" "$TASK_PACKAGE/database_v186.py" --check
stop_writers
"$TASK_PYTHON" "$TASK_PACKAGE/database_v186.py" --backup
"$TASK_PYTHON" "$TASK_PACKAGE/install_v186.py" --apply
"$TASK_PYTHON" "$TASK_PACKAGE/install_v186.py" --verify-installed
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
bash "$TASK_PACKAGE/verify_postgres_v186.sh"
"$TASK_PYTHON" manage.py collectstatic --noinput
resume_writers
printf '%s\n' 'v186 seasonal prices deployed. Summer: 1 May–31 October. Winter: 1 November–30 April.' 'Set each room/studio rate in Accommodation details or Django admin. Existing agreed totals were preserved.'
