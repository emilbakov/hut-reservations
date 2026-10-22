SummitDesk v51 — Seven-day capacity utilization
Requires v50. No migrations. Read-only, manager-only.
Install: unzip -o summitdesk_v51.zip && python3 v51_package/install_v51.py
Then: python -m py_compile floorplans/staff_hub.py floorplans/forecast_utilization_v51.py && python manage.py check
Restart Gunicorn only if checks pass. Review manager and cleaner access.
