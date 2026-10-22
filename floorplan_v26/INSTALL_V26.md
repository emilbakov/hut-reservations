# SummitDesk V26 — Email invitations and cleaner onboarding

## Compatibility
Requires V24 HutCleaner, V25 staff_tasks.access, `floorplans:cleaner_team` and `floorplans:staff_tasks` routes, and Django's default username-based User model / ModelBackend. An SMTP email backend must be configured to actually deliver invitations. Test in staging before production. Cleaners are created with `is_staff=False`.

## Upload and install
PowerShell:
```powershell
scp "$HOME\Downloads\floorplan_cleaner_invitations_v26.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```
Ubuntu:
```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_cleaner_invitations_v26.zip -d floorplan_v26
cp floorplans/models.py floorplans/models.py.backup.v25
cp floorplans/urls.py floorplans/urls.py.backup.v25
cp floorplan_v26/floorplans/cleaner_invitations.py floorplans/
cp floorplan_v26/floorplans/staff_invitations.py floorplans/
cp floorplan_v26/floorplans/templates/floorplans/cleaner_invitations.html floorplans/templates/floorplans/
cp floorplan_v26/floorplans/templates/floorplans/cleaner_accept.html floorplans/templates/floorplans/
```

At END of `floorplans/models.py`, add:
```python
from .cleaner_invitations import CleanerInvitation
```

In `floorplans/urls.py`, add:
```python
from . import staff_invitations as invitations26
```
Inside existing urlpatterns add:
```python
path('<int:hut_id>/cleaning-invitations/', invitations26.cleaner_invitations, name='cleaner_invitations'),
path('cleaning-join/<str:token>/', invitations26.cleaner_accept_invite, name='cleaner_accept_invite'),
```
Both paths are relative to your existing `floorplans` URL include. The `floorplans` namespace must already exist. **Do not replace the existing urlpatterns.**

## Email configuration
Set `DEFAULT_FROM_EMAIL`, `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `EMAIL_USE_TLS` or `EMAIL_USE_SSL` as appropriate for your mail provider, using secrets outside version control. The invitation URL uses the current request host; set `ALLOWED_HOSTS`, use HTTPS, and configure `SECURE_PROXY_SSL_HEADER` appropriately behind Nginx if needed. Never expose invitation URLs in public logs or screenshots.

## Database (production PostgreSQL)
Back up your production database before migration:
```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py makemigrations floorplans
python manage.py sqlmigrate floorplans <NEW_MIGRATION_NUMBER>  # optional review
python manage.py migrate floorplans
python manage.py check
sudo systemctl restart gunicorn.service
```
Review the generated migration: it should only create CleanerInvitation. Do not run with default SQLite settings.

## Test
1. Manager visits `/staff/floorplans/3/cleaning-invitations/` (change hut ID).
2. Invite an email that does not belong to an existing Django user. Verify the mail is delivered.
3. Open the link in a private browser, set a username and strong password. Check the user has `is_staff=False` and a HutCleaner membership for the correct hut.
4. Verify the cleaner sees only their assigned tasks and cannot use Django Admin or another hut's pages.
5. Verify reused/revoked/expired links are rejected. Verify managers cannot invite for other huts.

## Scope and caveats
Existing users are added through V24 cleaning-team page, not via invitation. Email ownership is checked by possession of the link. Invite links expire in 3 days and are single-use. This patch does not change V25 tasks or automatically assign any task. Usernames must be unique. The onboarding view assumes default username-based auth; adapt before use with custom email-only user models or authentication backends. Email send failures do not leave active invitations. Invite links in an email are sensitive secrets.
