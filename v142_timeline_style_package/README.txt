SummitDesk v142 — Property Calendar styled like /staff/availability/week/

Changes ONLY floorplans/templates/floorplans/property_calendar_v138.html:
- Reservation timeline look: room rows, date headings, colored multi-night booking bars
  with guest names and bed counts; pending reservations in amber.
- Retains the current month plus 14 days (not the seven-day weekly view).
- Keeps the right-side quick-stay form, arrival/departure selection, guest name,
  price estimate, existing server-side validation and booking POST unchanged.
- Existing /staff/availability/week/ is not modified.
- Guest names are rendered only for reservations already authorized by the view.
- The bars are assembled client-side from the existing per-day booking data.

Requires an unmodified v140 or v141 Property Calendar template. The installer
checks its exact SHA256, backs it up, and refuses unknown changes. If preflight
fails, STOP and provide the SHA256. Never force overwrite.

From project root:
  unzip -o summitdesk_v142_timeline_style.zip
  python3 v142_timeline_style_package/install_v142_timeline.py --check
  python3 v142_timeline_style_package/install_v142_timeline.py

Tests (test-only SSL override may be needed if SECURE_SSL_REDIRECT=True):
  source myprojectenv/bin/activate
  python manage.py test floorplans.test_quickstay_v140 --settings=config.settings

Refresh browser (Ctrl+F5). No migrations, static collection or Gunicorn restart
normally needed for template-only changes unless templates are cached.

Rollback:
  python3 v142_timeline_style_package/rollback_v142_timeline.py --list
  python3 v142_timeline_style_package/rollback_v142_timeline.py --check BACKUP_PATH
  python3 v142_timeline_style_package/rollback_v142_timeline.py BACKUP_PATH
