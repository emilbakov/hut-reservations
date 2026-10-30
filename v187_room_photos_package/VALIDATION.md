# Validation

- Full Django bookings + floorplans regression suite: 892 tests, OK, skipped 10 PostgreSQL-only tests; 18.723 seconds. Isolated SQLite database and synthetic data.
- 11 new photo tests passed: blank default, no placeholder for blank image, scoped manager upload, rooms/ storage, preservation of seasonal rates/capacity/booking total, booking display with and without dates, no homepage/directory image, invalid-image rejection, retaining an existing photo, clearing a photo while preserving the stored file, cross-hut access refusal, multipart form/admin inline, escaped alt text.
- Migration executor verified: blank image after upgrade, existing rates and seasonal 110.00 booking total preserved, pre-photo historical Room ORM inserts still compatible with the retained additive column.
- Guarded installer/source rollback: 16 checks passed, including exact source restore, idempotence, custom source/prerequisite refusal, damaged payload and symlink refusal, mode preservation and recovery after an injected partial-write failure.
- Maintenance simulation: 5 normal/failure/retry scenarios passed, retaining original active-unit state and socket-before-service ordering.
- Django makemigrations --check --dry-run: no changes detected. Python and shell syntax checks passed.
- Source payload bytes and hashes verified against the tested checkout; ZIP integrity checked.

The checkout was reconstructed from the existing application and authoritative v183.1/v184/v185/v186 packages. No generated/example photos are included in the deliverable. No live site was accessed and no production data was changed.

A PostgreSQL server is unavailable in the local build environment. The deployment wrapper runs the full isolated PostgreSQL verification before restarting the site.
