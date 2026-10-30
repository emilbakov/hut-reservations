#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
TASK_PYTHON="$PWD/myprojectenv/bin/python"
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
TASK_TEST_OWNER="$("$TASK_PYTHON" -c 'import django;django.setup();from django.conf import settings;print(settings.DATABASES["default"]["USER"])')"
TASK_TEST_SUFFIX="$("$TASK_PYTHON" -c 'import secrets;print(secrets.token_hex(4))')"
TASK_TEST_DB="summitdesk_v180_test_$(date +%s)_${TASK_TEST_SUFFIX}"
# This database is created here, contains only synthetic tests, and is removed here.
# No live schema, password, role or reservation is changed by this verification.
sudo -u postgres createdb --owner="$TASK_TEST_OWNER" "$TASK_TEST_DB"
trap 'sudo -u postgres dropdb --if-exists "$TASK_TEST_DB"' EXIT
export HUT_DEPOSIT_TEST_DB="$TASK_TEST_DB"
"$TASK_PYTHON" manage.py test bookings floorplans --settings=config.settings_deposit_pg_test_v180 --keepdb --noinput
printf '%s\n' 'Isolated PostgreSQL regression and real concurrency checks passed.'
