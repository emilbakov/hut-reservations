# SummitDesk V29 — Navigation on all staff reservation screens

## Scope
This patch inserts the **existing V28** `{% summitdesk_nav %}` into staff templates in place, with per-file backups. It does **not** replace reservation views, business logic, existing templates, migrations, or URLs.

Included screens: arrivals/departures, operations, new reservation, reservation detail/edit, transfer review, calendar, dashboard, housekeeping, cleaning tasks, cleaner portal, team and invitations (where present).

The script is idempotent: templates already containing `{% summitdesk_nav %}` are skipped. Templates without an HTML `<body>` are skipped for manual review. Missing templates are skipped. Only HTML templates are changed.

## Upload (Windows PowerShell)
```powershell
scp "$HOME\Downloads\floorplan_navigation_v29.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## Install (Ubuntu)
```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_navigation_v29.zip -d floorplan_v29
python3 floorplan_v29/install_v29.py
```

The script prints the timestamped `backups_v29_*` directory and updated/skipped templates.

## Verify production Django
```bash
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
sudo systemctl restart gunicorn.service
```

## Smoke test
- Manager: open calendar, arrivals, overview, new booking, reservation details/edit, and transfer review. Confirm sidebar renders and forms/actions still work.
- Cleaner: only dashboard and their cleaning tasks appear. Confirm no manager links.
- Test desktop and mobile. Confirm navigation does not overlap page controls.

## Rollback
Restore changed templates from the timestamped `backups_v29_*` directory created by the script, then restart Gunicorn.

## Limitations
- Existing V28 navigation currently highlights only its direct destination route; nested reservation detail/edit and transfer pages do not automatically highlight the Reservations item.
- The V28 shared navigation relies on the `floorplans.staff_tasks.access` helper and the Django request context processor.
- Templates not in the list or without a body tag are not modified.
- No live integration test was performed on your server.
