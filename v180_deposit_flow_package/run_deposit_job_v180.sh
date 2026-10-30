#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
case "${1:-}" in
  holds) exec myprojectenv/bin/python manage.py process_deposit_holds ;;
  mail) exec myprojectenv/bin/python manage.py deliver_deposit_notifications --limit 10 ;;
  *) exit 2 ;;
esac
