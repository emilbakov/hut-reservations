# V25 — Cleaner-only portal (upgrade from V24)

## Purpose
Allows authenticated, active cleaners to use hut-scoped assigned cleaning tasks without `is_staff=True` or Django admin access. Managers retain task assignment and team management. Cleaner tasks use a mobile-first separate template.

## Install
1. Back up `floorplans/staff_tasks.py` and `floorplans/templates/floorplans/cleaner_team.html`.
2. Copy package `floorplans/staff_tasks.py` into project `floorplans/`.
3. Copy `floorplans/templates/floorplans/cleaner_portal.html` and `cleaner_team.html` into project `floorplans/templates/floorplans/`.
4. Keep the V24 `HutCleaner` model and both existing URLs: `<int:hut_id>/cleaning-tasks/` and `<int:hut_id>/cleaning-team/`. No new URL or migration is needed.
5. In Django Admin create an active user with `is_staff=False`, set a secure password, and do NOT grant model permissions. From the V24 team page, add the user to the hut and assign a task.
6. Sign in as that user using your project's normal Django login page. If your project has no login route, configure Django auth login views; `login_required` redirects to `settings.LOGIN_URL`.
7. Open `/staff/floorplans/<hut_id>/cleaning-tasks/` while logged in. Despite `/staff/` in the path, Django admin `is_staff` is no longer required for this view.
8. Test: cleaner can view/update only assigned tasks; cannot add/delete tasks or access team page; cannot access other huts; no `/admin/` access. Manager retains all task controls.

## Production checks
Use `DJANGO_SETTINGS_MODULE=config.settings_postgres` and source `/etc/hut-reservations/postgres.env` before `python manage.py check`. Restart gunicorn after deploying.

## Notes
This is a cleaner-only *page*, not a separate authentication system. It reuses your Django login. It does not alter booking/bed allocation rules. Existing cleaner users can have `is_staff` revoked **only after confirming they need no other staff-only views**. Do not revoke staff access from managers. Team member selection lists active non-superusers; review privacy policy and user provisioning before inviting external accounts.
