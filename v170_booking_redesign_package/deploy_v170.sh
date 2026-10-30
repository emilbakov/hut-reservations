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
"$TASK_PYTHON" v170_booking_redesign_package/install_v170.py --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py makemigrations --check --dry-run
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" v170_booking_redesign_package/backup_database_v170.py
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" v170_booking_redesign_package/configure_main_hut_v170.py
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v170 booking redesign deployed. Hard refresh (Ctrl+F5).' 'The new date, room and live summary layout is at /book/.' 'The heritage homepage, history and six photographs remain at /.' 'See BOOKING_REDESIGN.md for the responsive booking experience.'
