SummitDesk v44 - 7-Day Operations Forecast CSV Export

Requires installed v43 and v38 forecast. No database migrations.
From project root:
  unzip -o summitdesk_v44.zip
  python3 v44_package/install_v44.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python -m py_compile floorplans/staff_hub.py floorplans/forecast_export_v44.py
  python manage.py check
  sudo systemctl restart gunicorn.service

Manager test: /staff/floorplans/3/hub/?forecast_export=csv
Expected: CSV with one row per forecast day, scoped to hut 3.
Cleaner/non-manager: must not receive CSV (existing staff hub permissions apply).

Installer backs up the two modified files and refuses repeat installation.
