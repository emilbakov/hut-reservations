# v184 — Normal rooms and Studios

Upgrade for the merged v183.1 installation. This package has not been deployed to your server.

## What changes

Each unit has an accommodation type: **Normal room** or **Studio**. The existing name, capacity and whole-unit nightly rate remain unchanged. Existing units start as Normal room; no type is guessed from their names. Mark the relevant units as Studios yourself after deployment.

Every unit also has English and Bulgarian extras, entered one per line. They are blank initially. Enter actual facilities only; the upgrade does not advertise an assumed kitchenette, bathroom, breakfast, view or other unverified feature. The guest's chosen language is used, with a language-labelled fallback when only the other language is configured. Text is escaped and length-limited.

The type and listed extras appear on guest booking cards, booking details, guest self-service, manual booking and secondary-hut information pages. Studio has a distinct badge. Both types retain exclusive reservation and whole-unit pricing; there is no automatic type surcharge, per-guest multiplication or change to existing reservation prices/deposit terms.

Managers can edit type and extras from **Edit type & extras** on each unit in the staff calendar or Room availability. The editor is restricted to the manager's own hut, requires sign-in and CSRF protection, and cannot change price, capacity, assignments or reservations. Superusers can also manage types/extras in Django admin, including a type filter on the Rooms list.

The previously prepared price-preview fix is included: the booking form declares its pricing basis and loads a new script URL (`public_hut_v184.js`) so an old cached per-bed script is not reused.

## 1. Upload — Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v184_room_types.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Extract and stage — Ubuntu

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v184_room_types.zip
python3 v184_room_types_package/install_v184.py
```

On production the installer validates current source hashes, prerequisites and the actual production environment. It stages only; source is applied by the deployment wrapper while writers are stopped. Unknown modifications are refused. Your merged calendar overview/filter is preserved.

## 3. Deploy

```bash
bash v184_room_types_package/deploy_v184.sh
```

The wrapper takes the shared deployment lock, pauses the previously active app/project jobs and cron, checks for unmanaged workers, creates a private full PostgreSQL archive and source backup, applies source and migration `0030_room_types_v184`, then runs checks and isolated SQLite/PostgreSQL tests before collectstatic/reopening. Gunicorn's socket is started before its service. Only previously active units are resumed. On a required failure, writers remain stopped and their original state is retained for a retry; fix the reported error and rerun. Do not reverse the database migration.

No existing rooms, reservations, payments or policies are deleted. The migration adds type/extras and an allowed-type database constraint. Database defaults keep old source inserts compatible if source is rolled back. Prices, capacities and saved reservation totals are not converted or recalculated.

After deployment:

1. Refresh the staff calendar or Room availability.
2. Select **Edit type & extras** for a unit.
3. Choose **Studio** for studios, enter their actual extras in the appropriate language, and Save.
4. Check `/book/`: the badge and extras should appear. A 30-per-night unit must still cost 60 for two nights whether it holds one or three guests.

Existing nightly rates can still be managed through the established room-price controls; changing the type does not set a new price automatically.

## Backup and rollback

The deployment prints a private full database archive at `summitdesk_backups/room_types_v184_database_TIMESTAMP/` and a separate source backup at `summitdesk_backups/room_types_v184_TIMESTAMP/`. The archive contains private guest/payment data and password hashes; keep it private. The archive must pass `pg_restore --list` before migration; listing/checksum validation is not a trial restore.

To restore the previous SOURCE, use the actual source-backup directory printed during deployment:

```bash
bash v184_room_types_package/rollback_v184.sh summitdesk_backups/room_types_v184_TIMESTAMP
```

This restores the v183.1 interface/source while retaining the additive metadata columns, migration record and saved type/extras data. It does not delete reservations or reverse schema. A full database restore would overwrite later database changes and requires a separately reviewed recovery procedure.

## Validation

- Full local suite: **840 tests, OK (10 PostgreSQL-only checks skipped)**; 830 passed. Includes type defaults, constraints, hut scope, CSRF, superuser/unassigned-room access, length checks, escaped/localized extras, unchanged prices/totals and exclusive inventory for both types.
- Migration trial: existing units default normal, extras blank, rates/capacities/totals unchanged; legacy source inserts still work after migration.
- 16 installer/rollback checks, including altered hashes, corrupt payload, symlinks, idempotence, preserved modes, exact source restore and recovery from injected partial-write failure.
- 5 simulated maintenance/failure/retry scenarios, including socket-first startup and backup/migration/PostgreSQL-test failures.
- 103 templates compiled; Python/Bash checks passed. Actual browser preview displayed both types and studio extras, and one-to-three guests retained the same 60 total for a 30-per-night unit over two nights.
- Real PostgreSQL is unavailable locally. The deployment runs the isolated PostgreSQL suite on your server before reopening. Preview facilities/amounts are synthetic examples and are not installed as room data.
