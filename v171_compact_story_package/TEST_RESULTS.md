# v171 validation

- Full Django suite: 709 tests in 11.337 seconds; 703 passed, 6 PostgreSQL-only tests skipped under SQLite. No failures.
- Migration drift: no changes detected.
- 62 EN/BG story assertions: four chapters, removed 1977/source content, 2019 copy, photo/year selection, natural-scroll updates, reduced-motion behavior, native no-JavaScript fallback, six unique viewer images and correct focus restoration from duplicate links.
- 64 EN/BG booking assertions: v170 live estimates, initial result anchoring, date refresh, sold-out recovery, retained guest details, linked errors and navigation.
- Browser checks: short desktop story, manual selection of 2019/current view, natural phone PageDown updating the photograph, a horizontally scrollable archive rail and the six-image viewer with Escape dismissal.
- Phone/tablet checks at 320, 390 and 768 pixel outer frames: no page-level horizontal overflow; 320 px history controls measured 249 by 46 px. The history section measured about 1174 px high in the smallest frame, including the heading, photo and all four chapters.
- Both language renders checked for all active new translations and the absence of the old public 1977/source sections.
- Installer: 17 safety assertions passed, including hash checks, custom-edit refusal, payload corruption, symlinks, source modes, idempotency, failure recovery and guarded rollback.
- Production settings: 22 checks passed against the real project settings path, including actual preflight/install/verify without staged config/settings.py.
- Known v153.1, v168, v169 and v170 upgrades checked for read-only preflight, exact full installation, installed verification and exact source rollback.
- v170 booking templates/styles/scripts, original gallery/menu script, booking views/forms/services and financial Admin preserved byte-for-byte.

No production deployment or live PostgreSQL row-lock test was performed here. The supplied deployment script runs its checks and isolated tests again on the server before backup, migrations, static collection and Gunicorn restart.
