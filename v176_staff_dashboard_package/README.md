# v176 — Staff overview and shared language controls

The staff overview now follows the existing hut panel's visual style: a pale background, white rounded cards, green actions and a clear pending-work section. Today's decision, arrival, departure and actual check-in counts appear first. Pending requests keep their existing capacity checks, approval/decline forms, optional reason and undo workflow. The arrivals list, held-bed snapshot and monthly figures use the existing view data and hut permissions.

## Language-bar repair

Standalone pages such as `/staff/floorplans/1/hub/` rendered the language form without the stylesheet that `bookings/base.html` normally supplied. The shared staff navigation now loads its own scoped control stylesheet, giving both EN/БГ buttons a 44 × 44 px target and a visible active state.

The inclusion tag now supplies the request to the language form, so its `next` field preserves the current hut route and query parameters. The hub uses the actual HTML language and translated primary headings, metrics and actions. Detailed legacy reports retain their existing content.

The public homepage and booking layout keep their installed appearance. The already-authorized v175 guest-review email reliability fix and its journey tests are bundled for users upgrading directly from an earlier supported version. No new database migration or automatic booking/data update is introduced.

## Preview before installing

Extract the ZIP and open `previews/PREVIEW_dashboard_en.html` or `previews/PREVIEW_hub_en.html`. EN/БГ switches between their offline language previews. These files use synthetic guests and embedded assets; operational forms and navigation are not connected to your server.

## 1. Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v176_staff_dashboard.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu: install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v176_staff_dashboard.zip
python3 v176_staff_dashboard_package/install_v176.py
```

## 3. Ubuntu: deploy

```bash
bash v176_staff_dashboard_package/deploy_v176.sh
```

The wrapper loads `/etc/hut-reservations/postgres.env`, uses `myprojectenv/bin/python` directly, verifies source, runs checks and isolated regression tests, collects the new CSS and restarts Gunicorn. Test email uses the in-memory backend. Refresh with Ctrl+F5 after success.

Known v169, v170, v173, v174 and v175 source states are supported. The installer validates only the relevant files and its notification prerequisite, makes a source backup and refuses unknown edits before writing.

## Rollback

Use the exact source-backup path printed by installation:

```bash
bash v176_staff_dashboard_package/rollback_v176.sh summitdesk_backups/staff_dashboard_v176_TIMESTAMP
```

Replace `TIMESTAMP` with the printed timestamp. Rollback verifies source and backup integrity, restores the previous application files, recollects static assets and restarts Gunicorn. Booking records and notification data remain.
