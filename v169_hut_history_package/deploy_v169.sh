#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test -f manage.py
test -f /etc/hut-reservations/postgres.env
test -x myprojectenv/bin/python
TASK_PYTHON="$PWD/myprojectenv/bin/python"
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
"$TASK_PYTHON" v169_hut_history_package/install_v169.py --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py makemigrations --check --dry-run
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" v169_hut_history_package/backup_database_v169.py
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" v169_hut_history_package/configure_main_hut_v169.py
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v169 Studenets history and archive deployed. Hard refresh (Ctrl+F5).' 'The hut history and six photographs are at /. Reservation requests remain at /book/.' 'See HUT_HISTORY.md for historical sources, photo credits and dates.'
