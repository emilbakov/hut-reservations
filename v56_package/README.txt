SummitDesk v56 — Capacity Watch Severity Filter
Prerequisite: v55 installed and operational.
Install: python3 v56_package/install_v56.py
New GET parameter: capacity_level=all|critical|warning|notice
Only the on-screen v53 warning list is filtered. v55 totals and v54 CSV remain unfiltered.
No migrations. Verify python manage.py check and manager/cleaner access before restarting.
