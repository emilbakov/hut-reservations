# v177 — Hut directory and secondary hut pages

Redesigns `/huts/` and the information pages for both secondary huts using the cream, forest green and serif styling of the existing public homepage. The configured main hut appears first in the directory. Name/location search remains a native GET form, with a clear empty state.

Secondary hut pages display their existing photograph, description, active rooms, listed capacity, public contact details and directions. They stay information-only: no date picker, guest form, live availability promise or prices. Direct reservation POSTs remain forbidden. The main homepage, history, booking layout and staff area are not replaced by this package. No model or migration changes are included; no hut data, photos or contacts are overwritten.

English and Bulgarian interface text is included. Names and descriptions continue to come from your existing hut records. Missing photographs get a labelled illustration. Missing details are handled without inventing contact details or claims.

## Offline preview

Extract the ZIP and open `previews/PREVIEW_directory_en.html`. The two example secondary pages are linked from it; use EN/БГ to switch preview languages. Images, styles and fonts are embedded. Preview hut names, descriptions, rooms and contact details are illustrative and are never installed in the live database. Preview search, booking, external navigation and staff actions are disconnected; functional search and booking restrictions are tested in Django.

## 1. Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v177_huts_redesign.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu — install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v177_huts_redesign.zip
python3 v177_huts_redesign_package/install_v177.py
```

## 3. Ubuntu — deploy

```bash
bash v177_huts_redesign_package/deploy_v177.sh
```

The wrapper loads `/etc/hut-reservations/postgres.env`, uses `myprojectenv/bin/python`, verifies source, runs Django checks and isolated tests, collects static assets and restarts Gunicorn. Press Ctrl+F5 after success and check `/huts/` and each secondary hut. Known v169, v170, v173, v174, v175 and v176 source states are accepted; unrelated files retain their installed versions. Customized relevant files cause a refusal before writing.

## Rollback

Use the exact backup path printed by the installer:

```bash
bash v177_huts_redesign_package/rollback_v177.sh summitdesk_backups/huts_redesign_v177_TIMESTAMP
```

Replace `TIMESTAMP` with the printed value. The wrapper restores the previous relevant source, collects static assets and restarts Gunicorn. Hut and reservation records remain intact.

## Verification

732 tests ran in 15.022 seconds: 726 passed and 6 PostgreSQL-only concurrency tests were skipped under SQLite. Five new regression tests cover directory search and main-hut ordering, both secondary routes, forbidden booking writes, active-room/contact visibility, bilingual CSRF language switching and preservation of the main public templates.

56 installer/rollback checks passed across six supported source baselines. They cover read-only checks, source hashes, permissions, idempotence, exact rollback, customizations, corrupted payloads, symlinks, injected write failure and protection of later edits. 22 production environment checks passed using installed project settings rather than staged settings.

Browser QA used local synthetic pages: desktop directory and hut detail; 320 px Bulgarian directory; 390 px Bulgarian detail; 44 px language targets, 52 px contact targets and mobile menu/Escape behavior. No production records were read or changed. Live browser inspection was blocked by the server certificate reporting `ERR_CERT_COMMON_NAME_INVALID`; this release does not change TLS configuration.
