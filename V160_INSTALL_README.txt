SummitDesk v160 — footer links right-column fix

Purpose: ensure footer Useful Links are pinned to the far right even if
Contact details are not configured. Navbar is unchanged.

Prerequisite: v158/v159 layout already installed.
Apply by extracting at /home/deploy/hut-reservations.
Run python manage.py test --settings=config.settings_test before restart.
Run collectstatic using /etc/hut-reservations/postgres.env, then restart Gunicorn.
No database migrations.
