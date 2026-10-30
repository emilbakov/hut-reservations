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
"$TASK_PYTHON" v173_history_edit_package/install_v173.py --verify-installed
"$TASK_PYTHON" manage.py check
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'v173 history edit deployed. Hard refresh (Ctrl+F5).' 'Existing layout retained. The 1977 row is replaced by modernisation completed in 2021; historical notes removed.'
