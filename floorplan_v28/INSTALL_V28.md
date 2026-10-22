# SummitDesk V28 — Shared Navigation & Staff Homepage

## Scope
V28 introduces a shared top bar and responsive side navigation to V20/V22/V24/V25/V26/V27 staff pages, plus a role-aware `/staff/floorplans/` landing URL. It preserves existing reservation and housekeeping business logic. No migrations.

## Upload (Windows PowerShell)
```powershell
scp "$HOME\Downloads\floorplan_staff_shell_v28.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## Install (Ubuntu)
```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_staff_shell_v28.zip -d floorplan_v28
# Back up current templates before copying: some deployments may have local customizations.
mkdir -p backups_v28
for f in staff_hub staff_calendar staff_housekeeping staff_tasks cleaner_portal cleaner_team cleaner_invitations; do
  [ ! -f "floorplans/templates/floorplans/$f.html" ] || cp "floorplans/templates/floorplans/$f.html" "backups_v28/$f.html"
done
cp -r floorplan_v28/floorplans/templatetags floorplans/
mkdir -p floorplans/templates/floorplans/includes
cp floorplan_v28/floorplans/templates/floorplans/includes/summitdesk_nav.html floorplans/templates/floorplans/includes/
cp floorplan_v28/floorplans/staff_home.py floorplans/
# IMPORTANT: Only copy templates that match your installed V20–V27 versions.
cp floorplan_v28/floorplans/templates/floorplans/*.html floorplans/templates/floorplans/
```

## Add one URL
In `floorplans/urls.py`, import:
```python
from . import staff_home as home28
```
Inside `urlpatterns` add:
```python
path('', home28.staff_home, name='staff_home'),
```
The floorplans URLs must already be included under `/staff/floorplans/` for this landing URL to work. Keep the existing V27 `staff_hub` route and all other routes.

## Optional login redirect
If using Django's built-in login flow, set `LOGIN_REDIRECT_URL = '/staff/floorplans/'` in your production settings. If your login flow already has a custom redirect, integrate this route there instead. **Do not change `LOGIN_URL` or make the homepage public.**

## Verify on production PostgreSQL
```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
sudo systemctl restart gunicorn.service
```

## Smoke test
1. Manager: `/staff/floorplans/` redirects to an authorized hut dashboard; manager navigation visible.
2. Cleaner with `is_staff=False`: same URL redirects to authorized hut; only Dashboard/My tasks visible.
3. Verify calendar, housekeeping, tasks, team, invitations render and POST actions still work.
4. Test narrow/mobile viewport; no database migration is needed.

## Notes
- Templates are based on the V20–V27 versions built in this series. Compare them with your production templates before overwriting local edits.
- Existing standalone pages outside the included set (e.g. arrivals or reservation edit) retain their old layouts; this patch does not claim to unify every page.
- The Django template request context processor must be enabled (`django.template.context_processors.request`, typical default) for the shared navigation tag. If not enabled, the navigation hides safely.
- The hub metrics are unchanged from V27.
