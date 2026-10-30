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
"$TASK_PYTHON" v177_huts_redesign_package/install_v177.py --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v177 huts directory and secondary hut pages deployed. Hard refresh (Ctrl+F5).' 'Check /huts/ and both secondary hut pages.'
