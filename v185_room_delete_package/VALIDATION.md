# v185 validation

- Full Django bookings + floorplans regression suite: 856 tests, OK, skipped 10 PostgreSQL-only tests; 81.239 seconds. Local SQLite test database, synthetic data only.
- New admin deletion suite: 16 tests, all passed.
- Guarded installer/source rollback: 16 checks passed, including exact file restore, idempotence, modified source/prerequisite refusal, corrupted payload refusal, symlink refusal, permissions preservation and injected partial-write recovery.
- Maintenance simulation: 5 scenarios passed — normal, service-only, database backup failure, migration-consistency failure, PostgreSQL-check failure. Failure retries preserved the original service state; socket restarted before service.
- makemigrations --check --dry-run: no changes detected.
- Python compilation and shell syntax checks passed.
- Existing source verified against all payload files of the authoritative v184 package before editing.
- ZIP entries and all source payload hashes checked against the tested checkout.

No live PostgreSQL instance was available locally. Actual PostgreSQL migrations/concurrency and backup tools are checked by the deployment wrapper on the server. No live server was accessed, no real rooms/reservations were deleted, and this upgrade was not remotely deployed.
