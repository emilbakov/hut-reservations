# SummitDesk v146 — UI/UX and superuser admin fix

One cumulative package for your uploaded source through v143, v145, or v145.1.
It includes the previous reliability fixes and CSV test correction, so no earlier package needs to be reinstalled.
Never run an older source installer after v146: its hashes refer to older files.

## What changes

- Public booking: guest count survives the hut-directory handoff, clear booking steps, quantity buttons, remaining-bed counter, room/date/guest/night summary, full stay total with currency, clear manager-approval wording, and a reachable mobile review bar.
- Date availability refresh preserves guest name, contact details and notes; changed availability reduces unavailable selections with an explanation. Network failure keeps the previous selection. Nearby alternatives use real availability. Without JavaScript, the alternative-date preview is a read-only POST that keeps entered details.
- Monthly planner: 7-day mobile and 14-day desktop windows, full period option, room filter, sticky room labels and dates, visible arrival/departure markers, checkout excluded, reset that keeps guest details, currency and full price calculation, and explicit status labels.
- Reservation previews show guest, room, actual arrival/departure, status and beds from the already-authorized property data. Other properties and mixed-hut guest information remain protected.
- Conflicts offer available rooms or nearby dates when those nights are represented in the calendar. Selecting an alternative preserves guest information; the server checks availability again on confirmation.
- Navigation names the weekly calendar and monthly planner clearly and uses one creation action in the shared header. Django Admin is linked for superusers.
- Superusers assigned as hut managers retain their normal Django Admin model permissions. Ordinary hut managers remain restricted.
- Shared buttons, text, spacing, focus states, error feedback, touch controls and mobile input sizes.
- Includes v145 private guest-link enforcement, reviewed guest changes, duplicate-submit protection, notification delivery screen and retry timer, plus the v145.1 safe-CSV regression fix.

## Install — your normal three steps

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v146_ui_ux.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v146_ui_ux.zip
python3 v146_ui_ux_package/install_v146.py
```

3. Deploy:

```bash
bash v146_ui_ux_package/deploy_v146.sh
```

The installer validates known source hashes and payload integrity before changes, saves a timestamped source backup and installs atomically. Customized/unrecognized files stop installation. A write failure triggers source restoration. Re-running the installer is safe.

Deployment loads your existing virtualenv and `/etc/hut-reservations/postgres.env`, selects `config.settings_postgres`, backs up the database in `/home/deploy/reservation-backups/`, applies migrations, checks the app, runs the complete test suite against an isolated in-memory test database, collects static assets, activates the notification retry timer, and restarts Gunicorn. Existing SMTP credentials remain in their environment file.

The release includes additive migration 0020 if it was not already applied. There are no additional v146 model migrations. A database backup failure or failed command stops deployment before its later steps. Deployment failures do not automatically roll back the earlier source installation.

If any command fails, stop and keep its error output. Do not continue with subsequent commands. The installer prints the exact backup directory for rollback.

## Rollback

List source backups:

```bash
python3 v146_ui_ux_package/rollback_v146.py --list
```

Use the exact backup printed by the installer:

```bash
bash v146_ui_ux_package/rollback_v146.sh summitdesk_backups/ui_ux_v146_TIMESTAMP
```

Rollback checks current files and backup hashes before restoring them. Later manual edits cause refusal instead of overwriting them. The wrapper manages the retry timer, collects static assets and restarts Gunicorn. Reservations and notification records are not deleted. The additive reliability tables and migration file are retained to keep database history consistent.

## Verify after deployment

- Sign out and back in, then hard-refresh with Ctrl+F5 to load the new scripts/styles.
- Superuser: open `/admin/`; Hut, Room and Reservation should be visible, including when assigned as a hut manager.
- Search for two guests, open a hut, select two beds and review the total. Change dates after entering details and confirm those details stay filled.
- Open the monthly stay planner, preview a reservation, choose arrival and departure, inspect the total/currency, reset, and try a conflict with available alternatives.
- Inspect the planner and booking page on your phone. The shorter calendar window and bottom review link should remain usable.

## Validation and limits

473 Django tests: 469 passed, 4 PostgreSQL-only concurrency checks skipped on SQLite. Nine new functional regression tests cover group matching, handoff, summaries, read-only preview, real alternatives, admin permissions, property isolation and error month recovery. 52 DOM interaction assertions cover the public flow and both desktop/mobile planner modes. JavaScript syntax checks, Django system checks and migration drift checks pass.

The cloud browser could not reach the isolated local preview, so visual rendering in a real desktop/mobile browser is not verified. DOM tests verify interaction logic and responsive mode selection, not pixel layout. PostgreSQL concurrency checks run only when a PostgreSQL test database is available; the production deployment script uses the isolated SQLite suite. No live server deployment, real guest booking or real email send was performed here.

Browser availability can become stale between viewing and saving; the existing server booking service remains authoritative. Email retry remains at-least-once delivery as documented in v145.
