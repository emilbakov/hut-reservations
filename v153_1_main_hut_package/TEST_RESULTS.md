# Validation

- Uploaded newer source baseline: 678 tests, successful, 6 PostgreSQL concurrency checks skipped on local SQLite.
- Integrated release: 699 tests, successful (693 passed, 6 skipped), including the newer deposit, cancellation, navigation and branding regressions.
- Django migration drift check: no changes detected.
- Existing 0026 schema upgraded to 0027 with synthetic bookings, payment/refund rows, cancellation settlements, deposit policy and public operator details preserved. The booking app has one migration leaf.
- 17 installer safety checks: reproduced the original Admin refusal; accepted the exact uploaded Admin; read-only checks; complete source equality after installation; preserved file permissions; idempotence; byte-correct rollback; unknown-edit aggregation; financial prerequisite verification; old migration refusal; corrupt payload refusal; symlink and directory refusal; automatic recovery after an injected write failure; refusal to roll back later edits or damaged backups.
- 11 main-hut selection checks: actual terminal input, non-interactive refusal, exact slugs, inactive huts, idempotence and retained operator settings.
- Deployment and rollback shell syntax checked; ZIP payload hashes and CRC verified.

These are local automated checks. The package has not been deployed to the live server, and PostgreSQL row-lock behavior and browser appearance have not been verified here.
