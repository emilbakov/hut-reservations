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
"$TASK_PYTHON" v153_1_main_hut_package/install_v153_1.py --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" v153_1_main_hut_package/backup_database_v153_1.py
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" v153_1_main_hut_package/configure_main_hut_v153_1.py
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v153.1 main-hut application deployed. Hard refresh (Ctrl+F5).' 'Your current Karlak layout, deposits and cancellation features are preserved.' 'Only the selected main hut accepts new public reservation requests. See MAIN_HUT.md.'
