# v168 — Studenets, the heart of the resort

A new public homepage built around the historic role of the hut and your five uploaded photographs. Warm ivory, forest green, local serif typography, a large winter hero, the original hut, a keyboard-accessible 1984/today switch, archive photographs and a full-image viewer replace the booking-first homepage.

**The story is at `/`. Reservations are at `/book/`.** All huts remains in the desktop and mobile navigation. Other huts stay information-only. The booking page starts with dates and rooms, with its large marketing photograph removed. Booking questions are available at `/book/#questions`.

This package includes the complete main-hut change. It supports your uploaded newer v167 source (`summitdesk_v126(4).zip` / `admin(2).py`) and v153.1. It retains the current Admin deposit settings, payment ledger, cancellation settlements, protected deletion, staff pages and guest receipt layout. The environment checker reads the actual project settings; it does not expect a missing settings file inside the package.

## Three-step installation

1. PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v168_heritage_home.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v168_heritage_home.zip
python3 v168_heritage_home_package/install_v168.py
```

3. Deploy:

```bash
bash v168_heritage_home_package/deploy_v168.sh
```

During deployment, choose Studenets if the main hut has not been set. An existing active main-hut selection is retained. The main-hut name, description, rooms, contact information and directions come from your current database. This design uses the Studenets photographs and story you supplied; set Studenets as the main hut in Admin → Public website settings.

The deployment runs source verification, Django checks, migration drift checks and isolated tests before a private database backup, additive migrations, main-hut setup, static collection and Gunicorn restart. It uses `myprojectenv/bin/python` directly and loads `/etc/hut-reservations/postgres.env`.

## Safeguards and rollback

The installer checks all packaged source hashes and the newer financial prerequisites before writing. Unknown customizations are listed together and refused. It creates a private source backup, recovers automatically from a source-write failure, and treats an already-installed package as a no-op. The original v153 migration branch is refused if it has unexpectedly reached the active migrations folder.

Use the exact source backup path printed by installation:

```bash
bash v168_heritage_home_package/rollback_v168.sh summitdesk_backups/heritage_v168_TIMESTAMP
```

Replace `TIMESTAMP` with the actual printed path. Rollback refuses later source edits and restores the previous source, collects static files and restarts Gunicorn. It retains additive migrations and database contents. Returning to older source restores that version’s booking rules.

No new schema is introduced beyond the existing main-hut migration `0027_main_hut_v153_1`. If you already deployed v153.1, the migration is already present.

See HERITAGE_HOME.md for photo behavior, languages and route compatibility, and TEST_RESULTS.md for the completed checks.
