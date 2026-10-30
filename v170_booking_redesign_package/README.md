# v170 — Karlak booking redesign

The separate /book/ page now matches the heritage homepage: Karlak logo, warm ivory and forest green, local serif/sans fonts, shared visual header/footer, and compact room cards. Dates and group size come first. A desktop sidebar mirrors the existing room and price summary; a mobile review bar keeps the total accessible. First availability searches open at the room results.

The homepage history and all six photographs are included. Only the configured main hut accepts public reservations; the other huts remain information-only. The current inventory, guest access, deposits, payments, cancellation settlements and staff operations are retained.

This cumulative package accepts the exact uploaded v167 source (summitdesk_v126(4).zip and admin(2).py), v153.1, v168 and v169. Unknown source changes are listed and refused before any write. There is no new database migration beyond the existing main-hut migration 0027_main_hut_v153_1.

## Three-step installation

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v170_booking_redesign.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v170_booking_redesign.zip
python3 v170_booking_redesign_package/install_v170.py
```

3. Deploy:

```bash
bash v170_booking_redesign_package/deploy_v170.sh
```

The deployment uses myprojectenv/bin/python directly and loads /etc/hut-reservations/postgres.env. It verifies source and production settings, checks Django and migration drift, runs isolated tests, backs up the database, applies additive migrations, retains or configures the main hut, collects static files and restarts Gunicorn. If the main hut has not yet been set, choose Studenets when prompted. Hard refresh with Ctrl+F5 when deployment succeeds.

The environment checker reads the actual project config/settings.py. It does not require that file inside the incremental package.

## Rollback

The installer prints the exact private source-backup path. To restore it:

```bash
bash v170_booking_redesign_package/rollback_v170.sh summitdesk_backups/booking_v170_TIMESTAMP
```

Use the actual printed path in place of TIMESTAMP. Rollback guards against later edits, restores the original source, collects static files and restarts Gunicorn. Additive migrations and database contents are retained. Returning to older source restores its booking rules.

See BOOKING_REDESIGN.md, HUT_HISTORY.md and TEST_RESULTS.md for behavior, historical sources and validation.
