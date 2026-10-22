# V10 — Room allocation reports

Adds a date-range room allocation summary, CSV export, and printable report to the existing V9 visual bed assignments page. No Python changes, migrations, or new URLs.

## Install

```bash
cd /home/deploy/hut-reservations
unzip -o floorplan_reports_v10.zip -d floorplan_v10
cp floorplans/templates/floorplans/visual_beds.html floorplans/templates/floorplans/visual_beds.html.backup.v9
cp floorplan_v10/floorplans/templates/floorplans/visual_beds.html floorplans/templates/floorplans/
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a; source /etc/hut-reservations/postgres.env; set +a
python manage.py check
sudo systemctl restart gunicorn.service
```

Visit `/staff/floorplans/<hut_id>/visual-beds/`, select a room and dates, then click Show beds. Export CSV or print.

**Privacy:** Reports include guest names. Store/share carefully.

**Interpretation:** Report is a snapshot of V6 bed assignments and closures overlapping the selected date range, not a nightly availability calculation. An unassigned bed is not confirmed available. The same bed may have multiple non-overlapping assignments within the selected date range.
