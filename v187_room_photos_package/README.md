# v187 — optional photos for booking room options

Requires v186 seasonal room prices. Adds one optional Room photo field for each normal room or studio. All existing fields start blank. No real or sample photos are bundled or assigned.

Photos appear only on the booking page's room options, with and without selected dates. They are not added to the homepage or hut directory. Blank photos produce no image/placeholder. Uploaded photos use a responsive cropped display with lazy loading, explicit dimensions and escaped alt text based on room and hut names.

## Deployment

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v187_room_photos.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu, already connected:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v187_room_photos.zip
python3 v187_room_photos_package/install_v187.py
```

This validates exact v186 source hashes and production settings. Production source is not changed at this step. Customized/incompatible files are refused; do not force overwrite them.

3. Deploy:

```bash
bash v187_room_photos_package/deploy_v187.sh
```

The wrapper takes the shared deploy lock, pauses previously active writers, verifies a full private PostgreSQL archive and source backup, applies source and additive migration 0032, runs Django checks and the full SQLite and isolated PostgreSQL suites, collects static files, and resumes the original units. Gunicorn socket starts before service. On failure, fix the reported error and rerun the same wrapper; it retains the original active-unit state and leaves writers stopped. Do not reverse migration 0032.

No rooms, bookings, payments, seasonal prices, or existing uploaded media are deleted or changed by this upgrade. Migration 0032 adds the optional blank photo field only.

## Add photos later

Leave the new fields blank for now. When ready:

- **Django admin > Rooms > open a room > Room photo**, choose an image and save. The Hut admin room inline also includes the field.
- Alternatively use the staff calendar's **Edit type & extras** link. The room details form now supports image uploads and clearing an existing photo. Existing hut-manager scope and CSRF protection remain.

The model field is `Room.image`, with `upload_to="rooms/"`. Files are stored under `MEDIA_ROOT/rooms/` and served through the existing `/media/` mapping. The rooms folder is created when the first file is uploaded; no directory or image must be manually created now. Existing hut photos in `huts/` remain separate.

Django's ImageField form validates image uploads. Changing or clearing a photo does not delete the previous stored file automatically. This avoids losing an existing upload; file cleanup is a separate operation. The photo is a public booking asset once uploaded.

## Roll back source

Pass the exact source backup directory printed during deployment:

```bash
bash v187_room_photos_package/rollback_v187.sh summitdesk_backups/room_photos_v187_TIMESTAMP
```

Replace TIMESTAMP with the actual printed source path, not the database archive directory. Rollback verifies current source and backup hashes, restores v186 source and restarts the previously active units. The photo migration, stored image paths and uploaded media are retained. Existing seasonal bookings remain supported by v186, so they do not block this rollback. No reservations, room records or uploaded files are removed.

Source backups: `summitdesk_backups/room_photos_v187_TIMESTAMP/`.
Database archives/checksums: `summitdesk_backups/room_photos_v187_database_TIMESTAMP/`.
Backups may contain sensitive guest data and are stored privately. Source rollback does not restore a prior database state.

See VALIDATION.md for checks and local PostgreSQL limitations.
