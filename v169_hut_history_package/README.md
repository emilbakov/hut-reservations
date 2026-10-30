# v169 — Studenets: history, archive and the heart of the resort

A new public homepage built around the historic role of the hut and your six uploaded photographs. Warm ivory, forest green, local serif typography, a large winter hero, the original hut, a keyboard-accessible 1984/today switch, archive photographs and a full-image viewer replace the booking-first homepage.

**The story is at `/`. Reservations are at `/book/`.** All huts remains in the desktop and mobile navigation. Other huts stay information-only. The booking page starts with dates and rooms, with its large marketing photograph removed. Booking questions are available at `/book/#questions`.

This package includes the complete main-hut change. It supports your uploaded newer v167 source (`summitdesk_v126(4).zip` / `admin(2).py`), v153.1 and v168. It retains the current Admin deposit settings, payment ledger, cancellation settlements, protected deletion, staff pages and guest receipt layout. The environment checker reads the actual project settings; it does not expect a missing settings file inside the package.

The homepage now includes the former border post, the 1936–1937 beginning, the 1946 fire and 1947 rebuilding, the Stenata piste and the 1960 lift proposals, the opening on 28 October 1964, and the facilities recorded in the 1977 guidebook. The newer archive postcard `retro-043.jpg` is included unchanged, with its archives.bg mark and original frame. English and Bulgarian text is provided throughout.

## Three-step installation

1. PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v169_hut_history.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v169_hut_history.zip
python3 v169_hut_history_package/install_v169.py
```

3. Deploy:

```bash
bash v169_hut_history_package/deploy_v169.sh
```

During deployment, choose Studenets if the main hut has not been set. An existing active main-hut selection is retained. The main-hut name, description, rooms, contact information and directions come from your current database. This design uses the Studenets photographs and story you supplied; set Studenets as the main hut in Admin → Public website settings.

The deployment runs source verification, Django checks, migration drift checks and isolated tests before a private database backup, additive migrations, main-hut setup, static collection and Gunicorn restart. It uses `myprojectenv/bin/python` directly and loads `/etc/hut-reservations/postgres.env`.

## Safeguards and rollback

The installer checks all packaged source hashes and the newer financial prerequisites before writing. Unknown customizations are listed together and refused. It creates a private source backup, recovers automatically from a source-write failure, and treats an already-installed package as a no-op. The original v153 migration branch is refused if it has unexpectedly reached the active migrations folder.

Use the exact source backup path printed by installation:

```bash
bash v169_hut_history_package/rollback_v169.sh summitdesk_backups/heritage_v169_TIMESTAMP
```

Replace `TIMESTAMP` with the actual printed path. Rollback refuses later source edits and restores the previous source, collects static files and restarts Gunicorn. It retains additive migrations and database contents. Returning to older source restores that version’s booking rules.

No new schema is introduced beyond the existing main-hut migration `0027_main_hut_v153_1`. If you already deployed v153.1, the migration is already present.

See HUT_HISTORY.md for photo behavior, languages and route compatibility, and TEST_RESULTS.md for the completed checks.
