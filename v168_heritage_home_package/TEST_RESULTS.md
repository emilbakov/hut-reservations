# Completed checks

- Django suite: **709 tests, successful; 703 passed and 6 PostgreSQL-only concurrency tests skipped on local SQLite.** Existing deposit, payment, cancellation, guest-link, approval and staff regressions are included.
- New tests cover the form-free story homepage, main-hut alias, separate booking form targets, real availability, CSRF, signed duplicate submissions, other-hut restrictions, Bulgarian copy, local photograph assets, source credits, safe metadata and escaped owner content.
- Django migration drift: no changes detected. The main-hut migration is the existing 0027 migration after the newer deposit and cancellation migrations.
- 26 EN/BG JavaScript checks: progressive photo access, Then/Now tabs, keyboard selection, viewer cycling, focus restoration and mobile-menu Escape.
- Browser checks: desktop homepage and archive story, photo switching and full-image viewer, Bulgarian navigation, mobile menu, booking transition, and narrow 320/390-pixel layouts. No horizontal overflow was observed. Language controls measure 44 × 44 pixels. The narrow booking header and date form were checked after responsive fixes.
- 17 installer safety checks on the uploaded newer source, plus v153.1 check/install/verify/rollback compatibility. Complete resulting source matched the reviewed release; rollback restored the previous source bytes. Unknown edits, corrupt payloads, symlinks, directories, later edits and damaged backups were refused.
- 22 production environment checks exercise the actual installer check/install/verify path with no packaged settings file. The unchanged real project settings are evaluated; unsafe settings are refused without printing secret values.
- Deployment and rollback shell syntax, payload hashes, archive bytes and ZIP CRC are checked before delivery.

The browser used isolated synthetic fixtures. Nothing has been deployed to the production server here. PostgreSQL row-lock behavior remains outside local SQLite verification.
