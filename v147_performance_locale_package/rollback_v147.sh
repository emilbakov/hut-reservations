#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/hut-reservations
test "$#" -eq 1 || { printf '%s\n' 'Usage: bash v147_performance_locale_package/rollback_v147.sh summitdesk_backups/performance_locale_v147_TIMESTAMP'; exit 2; }
source myprojectenv/bin/activate
set -a
source /etc/hut-reservations/postgres.env
set +a
export DJANGO_SETTINGS_MODULE=config.settings_postgres
python v147_performance_locale_package/rollback_v147.py "$1" --check
sudo systemctl disable --now summitdesk-notification-retry-v145.timer 2>/dev/null || true
python v147_performance_locale_package/rollback_v147.py "$1"
python manage.py check
python manage.py collectstatic --noinput
if test -f bookings/notifications_v145.py; then
  sudo systemctl enable --now summitdesk-notification-retry-v145.timer
fi
sudo systemctl restart gunicorn.service
sudo systemctl is-active --quiet gunicorn.service
printf '%s\n' 'Previous source restored. Booking data and additive reliability tables retained.'
