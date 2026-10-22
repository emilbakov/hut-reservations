SummitDesk v52 — Peak & Quietest Forecast Nights
Prerequisite: v51 installed.
From project root: python3 v52_package/install_v52.py
Then run: python -m py_compile floorplans/staff_hub.py floorplans/forecast_peaks_v52.py
Then run: python manage.py check
Restart gunicorn only after checks pass.
No migrations. Read-only. Installer fails closed and backs up modified files.
