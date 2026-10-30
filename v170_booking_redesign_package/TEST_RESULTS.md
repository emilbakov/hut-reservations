# v170 validation

- Full Django suite: 709 tests ran in 12.447 seconds; 703 passed, 6 PostgreSQL-only tests skipped under SQLite. No failures.
- Migration drift check: no changes detected.
- 64 English/Bulgarian interaction assertions passed: empty-price guidance, quantity changes, mirrored totals and room breakdowns, initial results anchor, date refresh, sold-out recovery, retained guest data, error focus/links and mobile navigation.
- Twelve synthetic HTML fixtures rendered successfully across both languages: initial, available, invalid guest submission, longer stay, invalid dates and fully booked. All 24 new translations checked. Synthetic full occupancy was rolled back.
- Browser QA: English native date search navigated to room results; two beds at 18 EUR for two nights displayed 72 EUR. Changing to three nights displayed 108 EUR in both summaries and retained the entered name and email.
- Responsive browser QA at 320, 390 and 768 pixel outer frames: no horizontal overflow; full native date values; 44 by 44 pixel quantity targets; compact mobile header. Bulgarian date and group errors remained visible and focused at 320 px.
- Installer: 17 safety assertions passed, including custom edits, source modes, payload corruption, symlinks, recovery from write failure, idempotency and guarded rollback.
- Production configuration: 22 checks passed against the real-project settings path, including actual preflight/install/verify without a staged config/settings.py.
- Additional v153.1, v168 and v169 upgrade checks: read-only preflight, complete installation, exact final source match, installed verification and exact source rollback.
- Original booking views, forms, services, calculator/availability JavaScript and financial Admin were verified byte-for-byte unchanged from v169.

No live production deployment or PostgreSQL row-lock test was performed here. The supplied server deployment script runs its checks and isolated tests again before the database backup, migrations, static collection and Gunicorn restart.
