# v153.1 — main hut, compatible with the newer v167 source

This replaces the original v153 package. It contains the complete main-hut change; do not install or run the original v153 first.

It is built against the uploaded `summitdesk_v126(4).zip` source and the exact uploaded `admin(2).py`. Your Admin deposit settings, deposit ledger, payment history, cancellation settlements, protected financial deletion and cancellation/deposit action remain intact. Your current Karlak logos, right-aligned navigation, language controls, footer, reservation links and public receipt layout are retained.

The Admin source changes only by adding the Main hut fieldset to Public website settings. The model change adds the main-hut choice and its validation. The new migration is **0027_main_hut_v153_1**, after your existing 0025 deposit and 0026 cancellation migrations.

## Install

PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v153_1_main_hut.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

On Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v153_1_main_hut.zip
python3 v153_1_main_hut_package/install_v153_1.py
```

Deploy:

```bash
bash v153_1_main_hut_package/deploy_v153_1.sh
```

If several huts are active, deployment lists their actual names and asks you to choose the main hut by number. You can change it later in Admin → Public website settings → Main hut.

## Safeguards

The installer validates all 26 changed source files and seven prerequisites before any source write. It accepts only the reviewed before/after contents, validates the packaged bytes, refuses symlinks and reports all unexpected paths together. It never force-overwrites an unknown customization. Unchanged financial modules and migrations are verified without being rewritten. It also refuses the original v153 migration if it has unexpectedly reached the active migrations directory, so the two migration branches cannot be mixed silently.

Installation creates a private source backup and prints its path and rollback command. A failed source write restores the previous source automatically. Reinstalling the same package creates no extra backup. The deployment checks and isolated tests run before the production database backup and additive migration, then the main-hut selector runs before Gunicorn restarts. Existing media and notification retry services are kept in place.

For a read-only installation check, run `python3 v153_1_main_hut_package/install_v153_1.py --check`. If a different customization is reported, keep the guard enabled and provide the listed current files for a merge.

## Rollback

Use the source backup path printed during installation:

```bash
bash v153_1_main_hut_package/rollback_v153_1.sh summitdesk_backups/main_hut_v153_1_TIMESTAMP
```

Substitute the actual printed path. Rollback verifies that source has not been edited since installation, restores the uploaded v167 source, collects static files and restarts Gunicorn. It retains the additive main-hut column, choice and migration record; it does not delete reservations or financial records. Restoring the previous source restores that version's public booking rules, including its ability to accept bookings for other huts.

The release includes automated regression tests for the main-hut homepage, all public booking entry points, informational huts, forged room IDs, CSRF, Bulgarian notices, Admin integration and selector changes. Local validation uses SQLite; production PostgreSQL behavior must be checked in the deployed environment. See MAIN_HUT.md for route and policy details.
