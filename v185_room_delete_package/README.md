# v185 — delete unused rooms and their beds from Django admin

Requires the v184 Normal room / Studio upgrade. This incremental package changes four files. It does not add or reverse migrations, change prices, delete rooms during deployment, or reset reservations.

## Deployment

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v185_room_delete.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu, already connected:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v185_room_delete.zip
python3 v185_room_delete_package/install_v185.py
```

The installer validates exact v184 source hashes and production settings. In production this step changes no source. Customized or incompatible files are refused; do not force overwrite them.

3. Deploy:

```bash
bash v185_room_delete_package/deploy_v185.sh
```

The wrapper pauses existing writers, verifies a private full PostgreSQL archive, backs up source, installs, checks migration consistency, runs Django checks and both the isolated SQLite and PostgreSQL regression suites, collects static files, and resumes previously active units. Gunicorn socket starts before Gunicorn service. PostgreSQL tests use a separate temporary database containing synthetic data. A failed wrapper leaves services stopped and retains their original state; fix the reported error and rerun this same wrapper. No live reservations are automatically removed.

## Delete a test room

Sign into Django admin with a superuser or an authorized staff account with Room deletion permission. Existing hut-manager admin restrictions remain.

1. Open Admin > Bookings > Rooms.
2. Tick the test room(s) you want to delete.
3. In Action choose **Delete unused rooms and their beds…**, then press **Go**.
4. Review the hut/room names and bed count. Press **Yes, delete these unused rooms and beds** to delete permanently, or **Cancel** to return without changes.

The existing standard Delete button remains protected. Use the new action to include unused beds.

The action removes the selected rooms, their unused physical beds, and their floor-plan positions/markers. It never deletes huts or other rooms. Any reservation item, including cancelled/old booking history, blocks deletion. Bed assignments, closures, housekeeping records/events/tasks and other operational dependencies also block deletion. Deactivate a room instead if history needs to be retained.

All selected rooms must pass. Confirmation rechecks dependencies with room and bed rows locked, in the same room order as booking services. All deletions and the admin deletion log run in one transaction. If a dependency blocks any selected room, the entire operation is rolled back. No emails are sent by this action.

## Roll back source

Use the exact source backup path printed during deployment, not the database archive folder:

```bash
bash v185_room_delete_package/rollback_v185.sh summitdesk_backups/room_delete_v185_TIMESTAMP
```

Replace TIMESTAMP with the actual path printed on your server. Source rollback checks current files and backup hashes before restoring. It restores the previous admin implementation; it does **not** restore rooms already deleted through admin. No database rollback is performed.

Backups are private under summitdesk_backups/room_delete_v185_... (source) and room_delete_v185_database_... (full PostgreSQL archive plus checksum). These may contain sensitive data. Restoring the database archive replaces database state and is a separate operation, not part of this source rollback.

## Validation

16 new targeted tests cover confirmation, 10-bed cleanup, floor-plan cleanup, preservation of other rooms/huts, deletion logging, empty rooms, active and cancelled reservations, bed assignments, closures, housekeeping, atomic multi-selection failure, rechecks, rollback after a late protected dependency, permissions and CSRF. The full regression result is recorded in VALIDATION.md. PostgreSQL cannot run locally in the build environment; the deployment wrapper performs real isolated PostgreSQL verification before restarting the site.
