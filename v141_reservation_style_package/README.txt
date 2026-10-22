SummitDesk v141 - Match Property Calendar styling to Reservation Calendar

Restyles the v140 Property Calendar with the visual language of the existing
v136 Reservation Calendar: dark pine headings, Outfit/DM Sans typography,
light sage calendar headers, availability colors, rounded panels, controls,
buttons and a matching booking sidebar. Preserves arrival/departure selection,
form fields, availability checks, CSRF, JavaScript and backend untouched.

Requires the unmodified v140 Property Calendar template.
If preflight fails, do NOT force overwrite. Supply the reported SHA256.

Install from project root:
  unzip -o summitdesk_v141_reservation_style.zip
  python3 v141_reservation_style_package/install_v141_style.py --check
  python3 v141_reservation_style_package/install_v141_style.py

Optional test:
  source myprojectenv/bin/activate
  python manage.py test floorplans.test_quickstay_v140 --settings=config.settings

If SECURE_SSL_REDIRECT is enabled, run tests with a secure test client or a
separate test-only override. Do not weaken production HTTPS settings.

No migrations, collectstatic or Gunicorn restart are needed for this template
change. Refresh the Property Calendar (Ctrl+F5). If production templates are
cached, restart Gunicorn after checks.

Rollback (use the exact path printed by installer):
  python3 v141_reservation_style_package/rollback_v141_style.py --list
  python3 v141_reservation_style_package/rollback_v141_style.py --check BACKUP_PATH
  python3 v141_reservation_style_package/rollback_v141_style.py BACKUP_PATH

Rollback v141 before attempting any v140 rollback.
