SummitDesk v40 — Manager Alert Priorities

Requires v39 installed (staff_alerts_v39.py and v39 template section).
Adds a read-only severity summary and the top five prioritized alerts on Staff Hub.
Uses the existing v39 alerts list; no database writes, no migrations, no new URLs.

From project root:
  unzip -o summitdesk_v40.zip
  python3 v40_package/install_v40.py
  python -m py_compile floorplans/staff_hub.py floorplans/alert_summary_v40.py
  python manage.py check
  sudo systemctl restart gunicorn.service

The installer makes timestamped backups of files it changes and refuses reinstallation.
