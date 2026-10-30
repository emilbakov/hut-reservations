# v188 — multiple photos for each room or studio

Install directly over **v186 or v187**. This ZIP includes the optional main-photo field from v187 if it has not been installed. It adds a separate gallery of additional photos, leaving every gallery empty by default. No sample/generated photos are bundled or assigned.

Existing main room photos remain first. Additional photos follow their Order value (ties use upload record order). If the main photo is blank, the first gallery photo leads. All photos remain optional.

## Deploy

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v188_room_gallery.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu, already connected:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v188_room_gallery.zip
python3 v188_room_gallery_package/install_v188.py
```

This validates exact v186/v187 source hashes and production settings without changing production source. Unknown customizations are refused. Do not force overwrite them.

3. Deploy:

```bash
bash v188_room_gallery_package/deploy_v188.sh
```

The wrapper takes the shared deployment lock, records/pauses previously active writers, verifies a private full PostgreSQL archive, backs up source, installs, applies the pending additive migrations, runs Django checks and the full SQLite and isolated PostgreSQL regression suites, collects static files and resumes the original units. Gunicorn socket starts before service.

From v186, migration 0032 adds the optional blank main-photo field before 0033 creates the additional-photo table. From v187, only 0033 is new. Neither migration changes saved room rates, booking totals, deposits, inventory or existing uploaded images. No galleries are populated automatically.

On wrapper failure, fix the reported error and rerun the same wrapper. Writers remain stopped and the original active-unit state is retained. Do not reverse migrations 0032/0033.

## Add and manage photos

- **Django admin > Rooms > open a room**: Room photo remains the main image. Under **Additional room photos**, add image rows, optional captions and Order values. Use the inline Delete checkbox to remove an additional photo record. Save the room.
- **Staff calendar > Edit type & extras**: the room details screen has the same main-photo field plus an Additional room photos section. Use **Add another photo** for more upload rows. Leave unused rows blank, or tick Delete on a photo you want removed. Save accommodation details.

Managers can only edit photos for their permitted rooms. Gallery IDs from another room are rejected. Django ImageField forms validate uploads. The entire form is validated before saving, so an invalid gallery image does not partially change prices, the main photo or other gallery records.

Main files use `MEDIA_ROOT/rooms/`. Additional files use `MEDIA_ROOT/rooms/gallery/`. Both are served by the existing `/media/` mapping. Directories are created on the first upload. No Nginx change or manual folder creation is required when existing hut-photo serving works.

Clearing/replacing a photo or deleting its gallery record does not automatically remove the previous image file from storage. This preserves uploaded media; file cleanup is separate. Caption text is escaped when used as image alt text. Without a caption, the room and hut names provide the alt text.

## What guests see

Photos appear **only in booking room options**, including refreshed availability after changing dates. The homepage and hut directory do not show room galleries.

Guests can swipe horizontally, use previous/next controls, click thumbnails or use arrow keys in the focused photo strip. There is no autoplay; reduced-motion preferences are respected. With JavaScript unavailable, the images remain horizontally scrollable. Rooms without any photo keep their current layout with no photo placeholder. A single photo has no unnecessary navigation controls.

The unused-room admin deletion action removes associated gallery records when the room is otherwise safe to delete, while retaining uploaded files. Booking history, assignments, closures and housekeeping history remain protected.

## Source rollback

Use the exact source backup directory printed during deployment, not the database archive folder:

```bash
bash v188_room_gallery_package/rollback_v188.sh summitdesk_backups/room_gallery_v188_TIMESTAMP
```

Replace TIMESTAMP with the actual source backup path. The wrapper verifies source and backup hashes and checks gallery compatibility before and after stopping writers. Migrations and uploaded files are retained.

**If additional gallery records exist, source rollback is refused to preserve them.** Older source cannot manage the new gallery relationships during room deletion. Keep v188 and fix forward in that situation; the wrapper never deletes gallery records or files to force a rollback. Main photos by themselves do not prevent rollback. If the gallery migration has not been applied, restoring the previous source is allowed.

Source rollback restores the actual pre-install baseline (v186 or v187); it does not restore database state. Retained additive columns allow historical ORM inserts. Existing seasonal booking prices remain supported by both baselines.

Private source backups: `summitdesk_backups/room_gallery_v188_TIMESTAMP/`.
Private database archives/checksums: `summitdesk_backups/room_gallery_v188_database_TIMESTAMP/`.
These backups may contain sensitive guest data. Database archives do not contain uploaded media files.

See VALIDATION.md for the build checks and local PostgreSQL limitations.
