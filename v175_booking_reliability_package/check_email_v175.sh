#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test -f /etc/hut-reservations/postgres.env
test -x myprojectenv/bin/python
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
myprojectenv/bin/python v175_booking_reliability_package/check_email_v175.py "$@"
