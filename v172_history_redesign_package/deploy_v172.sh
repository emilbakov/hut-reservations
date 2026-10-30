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
"$TASK_PYTHON" v172_history_redesign_package/install_v172.py --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py makemigrations --check --dry-run
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" v172_history_redesign_package/backup_database_v172.py
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" v172_history_redesign_package/configure_main_hut_v172.py
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v172 clean photographic history deployed. Hard refresh (Ctrl+F5).' 'A static then-and-now photo pair and three short milestones replace the long history.' 'Includes modernisation from 2021. The 1977 section and historical notes are removed from the homepage.' 'See HISTORY_REDESIGN.md.'
