SummitDesk v115 — unified staff overview and navigation

Requires v113 and v114 installed.
Run from /home/deploy/hut-reservations:
  unzip -o summitdesk_v115.zip
  python3 v115_package/install_v115.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  sudo systemctl restart gunicorn.service

Backup directory printed by installer. Restore files from it if needed.
No database migrations. Only staff users see global management links; cleaner hut navigation stays scoped.
