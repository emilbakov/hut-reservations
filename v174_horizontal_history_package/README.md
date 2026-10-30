# v174 — Horizontal history, only this component

The historical timeline is now a horizontal row: 1936–1937, 1946–1947, the 1950s–1960, 1964 and 2021. Each period has a date, a short title and a short paragraph. A line connects the milestones; the completed modernisation in 2021 is highlighted.

On screens from 1200 px wide, all five periods fit in one row. On smaller screens, the timeline scrolls sideways within its own component, with part of the next period visible on phones. It uses native scrolling and scroll snapping, without JavaScript. The track can receive keyboard focus for native arrow-key scrolling. Content remains available without JavaScript and prints in chronological order.

Only four application source files are changed: the existing history include, one new versioned stylesheet and the Bulgarian PO/MO translation catalogues. The homepage wrapper, hero, photographs, gallery, navigation, booking pages, shared CSS and backend source are unchanged. No database migrations or data updates run.

The 1977 section and historical-notes links remain removed. The 2021 copy says that modernisation was **completed** that year, as supplied by the owner.

Open `PREVIEW.html` from the extracted package to inspect the Bulgarian history block before installing. It is self-contained and makes no external requests; resize the browser window to inspect the horizontal layout. The preview itself is not installed into the website.

## 1. Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v174_horizontal_history.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu: install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v174_horizontal_history.zip
python3 v174_horizontal_history_package/install_v174.py
```

## 3. Ubuntu: deploy

```bash
bash v174_horizontal_history_package/deploy_v174.sh
```

After success, use Ctrl+F5. The wrapper loads the existing environment, uses `myprojectenv/bin/python` directly, checks the installation, collects the new stylesheet and restarts Gunicorn.

Supported source: v169, v170 or v173, including these known versions restored by previous rollback scripts. The installer backs up the exact previous four-file state and refuses unknown edits without source changes. It does not install the v171/v172 homepage redesigns.

## Rollback

Use the exact backup path printed by the installer:

```bash
bash v174_horizontal_history_package/rollback_v174.sh summitdesk_backups/horizontal_v174_TIMESTAMP
```

Replace `TIMESTAMP` with the printed timestamp. Rollback verifies source and backup integrity before restoring the previous component and restarting the application. Booking data is retained.
