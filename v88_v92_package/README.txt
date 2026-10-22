SummitDesk v88-v92 — combined, read-only manager tools.
Requires v83-v87. No migrations. No version labels in website headings.
Features: issue search, matching issue CSV, arrival readiness filter, matching readiness CSV, quick section navigation.

Install:
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v88_v92.zip
  python3 v88_v92_package/install_v88_v92.py

Verify:
  python -m py_compile floorplans/staff_hub.py floorplans/daily_tools_v88_v92.py
  python manage.py check

Test /staff/floorplans/3/hub/?operations=1
Search: ?operations=1&issue_kind=Conflict&issue_q=room
CSV: ?operations=1&issue_kind=Conflict&issue_q=room&daily_tools_export=issues
Readiness: ?operations=1&readiness_mode=review
CSV: ?operations=1&readiness_mode=review&daily_tools_export=readiness
Verify cleaner cannot access manager data, unauthorized user 403, cross-hut manager 403.
