# v186 — summer and winter prices for whole rooms and studios

Requires v185 (admin room deletion), including v184 room types and v183.1 whole-unit booking. This is an incremental package with an additive migration; it does not clear rooms, bookings, housekeeping, payments or deposits.

## Seasonal rules

- Summer: every occupied night from **1 May through 31 October**, inclusive.
- Winter: every occupied night from **1 November through 30 April**, inclusive.
- The arrival night is charged; checkout night is not.
- Prices apply to the entire room/studio. Guest count never multiplies a whole-unit rate; capacity still limits guests.
- A stay from 31 October to 2 November has one summer night and one winter night. For example, at synthetic rates 40.00 and 70.00, its total is 110.00 for either one or four guests in the same unit.
- On upgrade both seasonal rates are initialized from each existing room's saved nightly price. No actual summer/winter amounts are guessed.

## Deployment

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v186_seasonal_prices.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu, already connected:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v186_seasonal_prices.zip
python3 v186_seasonal_prices_package/install_v186.py
```

This production installer step checks exact source hashes and production settings; no source is changed until the wrapper below. Unknown customizations are refused. Do not force overwrite them.

3. Deploy:

```bash
bash v186_seasonal_prices_package/deploy_v186.sh
```

The wrapper uses the existing shared deployment lock, records/pauses active writers, verifies a private full PostgreSQL archive and source backup, installs source, applies migration 0031, runs Django checks and both the SQLite and isolated PostgreSQL regression suites, collects static files, and resumes previously active units. Gunicorn socket starts before service. A failed deployment leaves writers stopped and retains the original state for retry: fix the reported error and rerun the same wrapper. Do not reverse the database migration.

PostgreSQL tests run against a temporary database with synthetic data, not the live database. The package does not change PostgreSQL roles/passwords or Nginx settings.

## Set the real prices

Open the staff calendar, use **Edit type & extras** beside a room, and set:

- **Summer price / unit / night**
- **Winter price / unit / night**

The same fields are available in **Django admin > Rooms** and the Hut room inline. Normal rooms and studios can have independently configured prices. Negative rates are rejected. Zero is a valid rate, so enter it only deliberately.

The old nightly field is now labelled **Fallback price / unit / night**. It is used only if a seasonal field is blank. Changing the fallback alone does not override filled summer/winter fields.

The booking page shows a breakdown for selected dates, and both seasonal rates before dates are chosen. Staff booking previews and the property planner calculate each night using the same boundaries. New static script URLs prevent cached whole-unit previews from continuing to use the old flat-rate calculation. English and Bulgarian labels are included.

## Existing and new reservations

Existing items retain their exact old flat nightly snapshots, including historical per-bed items. Migration does not recalculate old totals, deposit targets or recorded funds.

New seasonal bookings store their agreed summer/winter rates. Changing room prices afterward does not reprice those bookings, including pending requests. Guest receipts and private guest pages display the saved seasonal breakdown. Deposits use the resulting booking total. Booking-value reports allocate each night's saved rate to its actual month.

Changing dates on an existing seasonal allocation keeps that allocation's agreed seasonal rates. Existing flat-rate allocations keep their flat rate. Newly added room allocations use current rates. Existing restrictions on modifying an approved deposit hold remain; withdraw the hold first. An existing seasonal allocation cannot have its saved rate/room overwritten directly; replace the allocation when intentionally quoting different terms. Explicit flat-price overrides in Django admin remain flat-price snapshots.

## Source rollback

Use the exact source backup directory printed during deployment, not the database archive directory:

```bash
bash v186_seasonal_prices_package/rollback_v186.sh summitdesk_backups/seasonal_v186_TIMESTAMP
```

Replace TIMESTAMP with the printed source backup path. The wrapper verifies source/backup hashes and checks pricing compatibility before and after stopping writers. Migration 0031 and saved seasonal room settings are retained.

**If any seasonal-priced reservation items exist, including cancelled/history records, source rollback is refused.** Older code cannot correctly calculate those saved rates. Keep v186 and fix forward in that situation. No reservation is deleted or repriced to make rollback possible. If migration failed before adding the snapshot column, restoring the previous source is allowed.

Source rollback does not restore rooms deleted through admin and does not restore an earlier database. Full database restoration is a separate operation with consequences for all data created since the archive; never perform it casually to undo source changes.

Private source backups: `summitdesk_backups/seasonal_v186_TIMESTAMP/`.
Private database archives/checksums: `summitdesk_backups/seasonal_v186_database_TIMESTAMP/`.

See VALIDATION.md for build checks and local PostgreSQL limitations.
