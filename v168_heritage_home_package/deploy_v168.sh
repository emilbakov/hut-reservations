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
"$TASK_PYTHON" v168_heritage_home_package/install_v168.py --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py makemigrations --check --dry-run
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" v168_heritage_home_package/backup_database_v168.py
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" v168_heritage_home_package/configure_main_hut_v168.py
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v168 heritage homepage deployed. Hard refresh (Ctrl+F5).' 'The hut story is at /. Dates, rooms and reservation requests are at /book/.' 'See HERITAGE_HOME.md for the photographs, language controls and main-hut settings.'
