SummitDesk v117 — Staff sign-in
================================
Requires v116 installed.

New routes:
  /staff/login/   — managers and cleaners, Django session login
  /staff/logout/  — POST-only logout, CSRF protected

Changes:
- Standalone SummitDesk-styled responsive staff login page.
- Manager accounts with active assigned huts -> /staff/dashboard/.
- Cleaner accounts with active assigned huts -> /staff/floorplans/ (redirects to their workspace).
- Admin users (superusers) -> dashboard.
- Users with no active hut access cannot sign in to staff area.
- Public landing page and public navigation point to the new staff login.
- Shared staff sidebar adds POST-only sign-out action.
- Existing @login_required staff views use /staff/login/ via LOGIN_URL.
- Legacy admin login prompts for /staff/ URLs redirect to the new staff login;
  normal /admin/login/ without a staff destination remains unchanged.
- No new users, passwords, database migrations or permission changes.

Install (from /home/deploy/hut-reservations):
  unzip -o summitdesk_v117.zip
  python3 v117_package/install_v117.py
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a
  python manage.py check
  python manage.py test bookings.test_staff_auth_v117
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service

If validation fails, DO NOT restart Gunicorn. Roll back:
  python3 v117_package/rollback_v117.py
  python manage.py collectstatic --noinput
  sudo systemctl restart gunicorn.service

Security:
- Uses Django AuthenticationForm, sessions and CSRF protection.
- External redirect destinations are rejected.
- Keep your site behind HTTPS before entering passwords. Production secure
  session and CSRF cookies may not work on plain HTTP.
- This update does not add brute-force rate limiting or password reset emails.
