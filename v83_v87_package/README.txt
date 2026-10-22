SummitDesk v83-v87: five features, one package.
Requires v78-v82 installed. No migrations, read-only, manager-only via existing Staff Hub access.

- Filter critical issues by conflict / arrival
- Seven-day arrival readiness summary
- Numbered-bed details CSV
- Daily checklist CSV
- Print-friendly operations report

No technical version labels are added to the website.

Install:
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v83_v87.zip
  python3 v83_v87_package/install_v83_v87.py

Check:
  python -m py_compile floorplans/staff_hub.py floorplans/daily_reports_v83_v87.py
  python manage.py check

Manager page: /staff/floorplans/3/hub/?operations=1
CSV: ?operations=1&daily_export=beds
CSV: ?operations=1&daily_export=checklist
Test a manager, a cleaner, an unrelated user, and a manager for another hut.
These reports reflect recorded data; unassigned beds are NOT necessarily available.
