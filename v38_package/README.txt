SummitDesk v38 — 7-day Operations Forecast

From project root, after uploading the ZIP:
  unzip -o summitdesk_v38.zip -d v38_package
  python3 v38_package/install_v38.py
  cp v38_package/staff_forecast_v38.py floorplans/staff_forecast_v38.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python -m py_compile floorplans/staff_hub.py floorplans/staff_forecast_v38.py
  python manage.py check
  sudo systemctl restart gunicorn.service

IMPORTANT: install_v38.py adds an import for staff_forecast_v38. Copy the module
before running manage.py check. Backups are created automatically.
No database migrations or reservation modifications.

Forecast semantics: seven calendar days including today; active rooms only;
confirmed and pending hold bed places; overlapping closures deduplicated by bed;
cleaning tasks counted by day. Does not represent unique guests.
