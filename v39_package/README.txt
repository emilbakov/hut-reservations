SummitDesk v39 — Read-only manager operations alerts

Run from /home/deploy/hut-reservations:
  unzip -o summitdesk_v39.zip
  python3 v39_package/install_v39.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python -m py_compile floorplans/staff_hub.py floorplans/staff_alerts_v39.py
  python manage.py check
  sudo systemctl restart gunicorn.service

Requires v38. Alerts use aggregate bed-place counts; do not infer exact bed assignment conflicts.
No migrations. No database writes. Installer backs up modified files.
