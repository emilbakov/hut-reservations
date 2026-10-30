# v183 — exclusive rooms, studios and apartments

Accepts original/replay-repaired v180 or v181 application source. The v181 Deposits dashboard and corrected booking replay test are bundled. v182 is a separate optional reservation-data reset and installs no application source. This upgrade does not clear any reservations and has not been deployed to your server.

Each Room record represents one rentable unit: room, studio or apartment. Use its name to identify the accommodation. Its existing `price_per_night` amount is now the WHOLE UNIT's nightly price, without multiplying by guest count or capacity. A saved price of 80 means 80 per night whether 1 or 4 guests use a four-person unit; two nights cost 160. Existing room-rate amounts are not changed or multiplied. Review the configured rates before reopening.

## Booking behavior

- A pending or confirmed reservation holds each selected unit exclusively. One guest blocks it from every other reservation for the overlapping nights. Checkout remains exclusive: another guest can arrive on departure day.
- Guest quantity is still recorded, must fit the unit capacity, and must match the requested group size on public bookings. Enter guests in each chosen unit; leave 0 to skip a unit. Several units can belong to the same group reservation, and each selected unit is charged once per night.
- The existing `beds` field now represents guests within an exclusively reserved unit, preserving integrations and physical bed assignments. Bed markers/cleaning tools remain available for operations; they do not make spare beds sellable.
- Public booking, staff manual/quick booking, transfers/date edits, admin model writes, the live public total, staff previews, calendar availability, reports/exports and deposit calculations use the new rules. The main-hut-only public booking policy is unchanged.
- Any bed maintenance closure makes its whole unit unavailable for that night. Manual cleaning readiness/tasks are unchanged.
- Cancelling or expiring an unpaid deposit hold releases the whole unit. The v180 approval/payment/reminder process is retained.

## Existing prices and migration

Migration `0029_whole_units_v183` adds a saved pricing basis to each reservation item. All EXISTING items are explicitly marked as legacy bed pricing, preserving their original totals, payments and approved deposit terms. NEW production bookings use whole-unit pricing. Subsequent guest-count changes do not multiply a new unit's nightly price. A price change on the unit does not reprice existing items.

Old reservations also block their rooms exclusively under the new inventory rules. The deployment refuses if different future active reservations already overlap in one unit. Resolve those records explicitly before retrying; the upgrade does not silently cancel guests. If they are test records you want removed, run the separately supplied v182 reset first.

The compatibility regression settings retain bed mode for the established bed-based tests; the new whole-unit suite explicitly runs room mode. Production `config.settings` sets `BOOKING_UNIT = "room"` and the deployment uses `config.settings_postgres`.

## 1. Upload — Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v183_whole_units.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Extract and stage — Ubuntu

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v183_whole_units.zip
python3 v183_whole_units_package/install_v183.py
```

On production this checks prerequisites, file hashes and the actual production environment. It does not replace live source. Unknown customizations are refused; do not force-overwrite them.

## 3. Deploy

```bash
bash v183_whole_units_package/deploy_v183.sh
```

The wrapper loads the existing PostgreSQL environment and virtual-environment Python. It checks future inventory, takes the shared maintenance lock, records the currently active project services/timers, pauses those writers and cron, checks for unmanaged application jobs, and creates a private FULL PostgreSQL archive before installing source or applying migration 0029. The archive must pass `pg_restore --list`; its checksum is recorded. No email or payment is sent by the deployment.

The source installer backs up every replaced file and prints its source-backup directory. After migration the wrapper runs Django checks, the full isolated SQLite regression suite, and the full isolated PostgreSQL suite (including the real whole-unit concurrency test), then collects static assets. The temporary PostgreSQL test database is separately named and removed afterward; no production role/password is changed.

The previously active services are restored, with Gunicorn's socket before its service. Cron is resumed if it was previously active. The site is unavailable during this maintenance. If a required step fails, writers remain stopped and the original service-state record is retained for a retry. Fix the exact reported error and rerun the wrapper; do not reverse the database migration.

After success, hard refresh `/book/`, staff booking and the calendar. Check one synthetic reservation with your own email: change 1 guest to the unit capacity, verify the same total, then confirm another booking cannot select that unit for overlapping dates. Also check approval/deposit amounts against the whole-unit total.

## Backup and source rollback

Database archives are created under `summitdesk_backups/whole_units_v183_database_TIMESTAMP/` (private directory, archive mode 0600). They contain the full database including guest/payment information and password hashes; keep them private. Source backups are separate under `summitdesk_backups/whole_units_v183_TIMESTAMP/`.

To restore the previous source, use the exact SOURCE backup printed by the installer:

```bash
bash v183_whole_units_package/rollback_v183.sh summitdesk_backups/whole_units_v183_TIMESTAMP
```

Rollback is refused if ANY whole-unit-priced reservation items exist, including cancelled records: older source would multiply their prices by guest count. Do not bypass this guard. Before any new whole-unit bookings, source rollback is available. It preserves the additive migration and its tiny import helper; a database default keeps legacy inserts compatible. It does not remove reservations, reverse migrations or restore a database archive. A full database recovery would replace later database changes and needs a separately reviewed recovery procedure.

## Validation

- Local full suite: 820 tests, OK with 10 PostgreSQL-only checks skipped (810 passed). This includes 18 whole-unit scenarios; one additional whole-unit concurrency test requires PostgreSQL.
- Migration trial verified old totals, unchanged room rates, new whole-unit totals and legacy insert compatibility.
- 24 installer/rollback checks: original hashes, idempotence, damaged/customized/symlinked files, modes, failure restoration and source rollback.
- 5 simulated deployment/failure/retry scenarios: socket/service order, service-only setup, backup failure, migration failure and PostgreSQL verification failure; original unit states restored on successful retry.
- The actual public summary function was executed for 1/2/4 guests and multiple units: price stayed constant per selected unit. Python, Bash and all 101 templates compiled.
- No PostgreSQL server/client is available locally. Real PostgreSQL migration, archive and concurrency checks are required on your server before reopening; no local PostgreSQL success is claimed. Archive listing/checksum is not a trial restore.
