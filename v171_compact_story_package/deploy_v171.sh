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
"$TASK_PYTHON" v171_compact_story_package/install_v171.py --verify-installed
"$TASK_PYTHON" manage.py check
"$TASK_PYTHON" manage.py makemigrations --check --dry-run
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_v145_test --noinput
"$TASK_PYTHON" v171_compact_story_package/backup_database_v171.py
"$TASK_PYTHON" manage.py migrate --noinput
"$TASK_PYTHON" v171_compact_story_package/configure_main_hut_v171.py
"$TASK_PYTHON" manage.py collectstatic --noinput
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v171 compact homepage story deployed. Hard refresh (Ctrl+F5).' 'Four short chapters and changing photographs replace the long history at /.' 'The 1977 section and historical-notes disclosure are removed; renovation through 2019 is included.' 'The v170 booking redesign remains at /book/. See SHORT_STORY.md.'
