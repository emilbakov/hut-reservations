# v188 validation

- Full Django bookings + floorplans suite: 909 tests, OK, skipped 10 PostgreSQL-only tests; 19.901 seconds. Synthetic data and an isolated SQLite database.
- 17 new gallery tests cover blank defaults, main-photo preservation, ordering, fallback without a main photo, two-image upload, rate/capacity/total preservation, editing captions/order, deletion with stored-file retention, cross-room photo-ID tampering, cross-hut access, invalid-upload atomicity, missing management forms, older metadata submissions, escaped captions, guest controls, no homepage/directory gallery, prefetch query count, staff editor, native admin inline, unused-room deletion and booking-history protection.
- 18 JavaScript navigation assertions passed using DOM test doubles: arrows, thumbnails, keyboard navigation, independent room galleries, reduced-motion behavior, single-image controls and reinitialization after availability refresh. New gallery/editor scripts passed Node syntax checks.
- 107 templates compiled.
- Migration executor confirmed: gallery starts empty, existing main-photo path retained, seasonal rates unchanged, saved 110.00 reservation total unchanged, historical ORM inserts compatible.
- Guarded v187 installer/source rollback: 16 checks passed, including idempotence, exact restore, customized source/prerequisite refusal, damaged payload and symlink refusal, permissions and partial-write recovery.
- Direct v186 installation and exact source rollback also passed. The package includes migration 0032 and the optional-photo files needed when v187 is absent.
- 5 maintenance simulations passed for normal/service-only operation and backup/migration/PostgreSQL-check failures, preserving original active state and socket-before-service ordering.
- 4 gallery rollback guard checks passed: absent table, empty gallery, existing gallery rows, wrong database vendor.
- makemigrations --check --dry-run: no changes detected. Python compilation and shell syntax checks passed.
- Baseline matched the authoritative v187 package. All source payload hashes/bytes verified against the tested checkout; ZIP integrity checked; no photos bundled.

No live site was accessed and no production photos, rooms, bookings, deposits or payments were changed. Actual PostgreSQL regression/concurrency checks and archive verification run during server deployment; no PostgreSQL server is available locally. Browser layout was not visually inspected in this build.
