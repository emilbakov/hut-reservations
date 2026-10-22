SummitDesk v43: filtered operations alerts CSV export
Prerequisite: installed v42 Staff Hub and dependencies.
Install: cd /home/deploy/hut-reservations && unzip -o summitdesk_v43.zip && python3 v43_package/install_v43.py
Checks: python -m py_compile floorplans/staff_hub.py floorplans/alert_export_v43.py; python manage.py check
Restart: sudo systemctl restart gunicorn.service
Export: /staff/floorplans/3/hub/?alert_level=warning&alert_q=capacity&alert_export=csv
Security: only hut managers can export. Cleaners and unrelated users cannot export.
CSV columns: Severity, Date, Title, Description. UTF-8 BOM for Excel; spreadsheet formula prefixes escaped.
Rollback: copy staff_hub.py and staff_hub.html from printed v43_backup_... folder into original locations; remove floorplans/alert_export_v43.py; restart gunicorn.
