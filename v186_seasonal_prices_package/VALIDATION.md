# v186 validation

- Full Django bookings + floorplans suite: 881 tests, OK, skipped 10 PostgreSQL-only tests; 42.134 seconds. Synthetic data in an isolated SQLite database.
- 25 new seasonal tests: boundaries (including leap day), summer and winter stays, both season crossings, checkout exclusion, whole-unit guest counts, saved-rate immutability, room price edits, date changes, legacy flat/per-bed preservation, zero and fallback rates, negative-rate constraints, exact form totals, real guest submission, guest receipt, manager editing, deposit calculation, partial-range reporting, monthly financial allocation, modification quote, staff booking and property calendar rendering.
- JavaScript: 13 integer-cent calculation checks passed, including season/year boundaries, leap day, daylight-saving dates, fractional currency, zero rates, fallback and invalid ranges. Both new booking/planner scripts passed Node syntax checks.
- Migration executor: existing room rates/capacity preserved; both seasonal fields initialized from saved rate; legacy total 72.00 unchanged; old historical ORM inserts remain compatible with additive columns.
- 106 templates compiled. One executable inline JavaScript block extracted from actual guest/staff/calendar responses passed Node syntax checks.
- 16 guarded installer/source rollback checks passed, including exact restore, idempotence, custom source/prerequisite refusal, corrupted payload/symlink refusal, mode preservation and partial-write recovery.
- 5 maintenance failure/retry simulations passed, preserving prior active state and socket-before-service ordering.
- 4 pricing rollback guard checks passed: no snapshot column, no seasonal items, existing seasonal items, wrong database vendor.
- makemigrations --check --dry-run: no changes detected. Python compilation and shell syntax checks passed.
- Baseline verified against authoritative v185 payload. All packaged source bytes/hash entries verified against the tested v186 checkout. ZIP integrity checked.

No PostgreSQL server was available locally. Real PostgreSQL regression/concurrency tests and backup verification run during server deployment. No production server was accessed, no live bookings were changed, and this ZIP has not been deployed remotely.
