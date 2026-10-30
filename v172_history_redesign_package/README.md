# v172 — Clean photographic history

The homepage story now pairs the original hut with the present-day hut. A short introduction and three moments — 1936–1937, 1964 and modernisation from 2021 — replace the long history and the changing-photo scroll interaction. All text and both photographs remain visible without JavaScript. The page no longer displays the 1977 section, renovation-through-2019 copy, or “Sources & historical notes” / “Източници и исторически бележки”.

## 1. Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v172_history_redesign.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu: install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v172_history_redesign.zip
python3 v172_history_redesign_package/install_v172.py
```

## 3. Ubuntu: deploy

```bash
bash v172_history_redesign_package/deploy_v172.sh
```

Refresh with Ctrl+F5 after successful deployment. The wrapper loads `/etc/hut-reservations/postgres.env`, uses `myprojectenv/bin/python` directly, verifies installed files, runs checks and isolated tests, makes a database backup, applies the existing additive migrations if needed, retains/configures the main hut, collects static assets and restarts Gunicorn.

This cumulative package accepts the known uploaded v167 source, v153.1, v168, v169, v170 and v171, including known source restored by v171 rollback. You do not need to install v171 first. It refuses unknown changes before writing source. The production check reads the real project settings; the package intentionally does not contain `files/config/settings.py`.

No new database migration is introduced. The v170 booking design and booking/backend/staff/financial source are preserved byte-for-byte. Names, photographs and the main-hut configuration are retained.

## Rollback

Use the exact backup path printed by the installer:

```bash
bash v172_history_redesign_package/rollback_v172.sh summitdesk_backups/history_v172_TIMESTAMP
```

Replace `TIMESTAMP` with the actual printed timestamp. Rollback verifies source and backup integrity, restores the previous code, collects static assets and restarts Gunicorn. Reservation data and additive migration history remain.

See `HISTORY_REDESIGN.md` and `TEST_RESULTS.md`.
