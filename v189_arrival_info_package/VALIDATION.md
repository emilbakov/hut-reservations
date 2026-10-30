# v189 validation

- Full Django bookings + floorplans regression suite: 929 tests, OK, skipped 10 PostgreSQL-only tests; 21.110 seconds. Synthetic data and isolated SQLite database.
- 20 new arrival tests passed: blank/default display; saving actual facts without repricing or sending mail; hut scope, authentication, superuser access and CSRF; invalid URLs/phones/times with no partial save; injected payment/name fields ignored; receipt and private portal display; cancellation keeps contacts and hides arrival notes; Bulgarian and language fallback; midnight and partial check-in windows; escaped text and unsafe map filtering; default/custom confirmation arrival content without duplication; default/custom pre-arrival details; confirmed-only pre-arrival eligibility; translation context preservation; queued body immutability/no resend after edits.
- Migration executor confirmed: new facts blank; original phone/email/map preserved; gallery retained; saved seasonal total 110.00 unchanged; historical Hut ORM inserts remain compatible.
- 109 templates compiled.
- 16 guarded installer/source rollback checks passed, including exact restore, idempotence, custom source/prerequisite refusal, damaged payload/symlink refusal, permissions and partial-write recovery.
- 5 maintenance normal/failure/retry simulations passed, preserving active-unit state and socket-before-service ordering.
- makemigrations --check --dry-run: no changes detected. Python compilation and shell syntax checks passed.
- Baseline verified against authoritative v188 payload. All source payload bytes and hashes verified against the tested checkout. ZIP integrity checked.

No live site was accessed and no production email was sent. Actual PostgreSQL regression/concurrency and archive verification run during server deployment; PostgreSQL is unavailable locally. Browser layout was not visually inspected in this build.
