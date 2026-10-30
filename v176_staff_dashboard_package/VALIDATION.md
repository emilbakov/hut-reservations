# v176 validation

Verified locally on 29 October 2026, using synthetic records and isolated test databases.

## Application regression

`manage.py test bookings floorplans --settings=config.settings_v145_test --noinput`

727 tests ran in 13.744 seconds: 721 passed, 6 PostgreSQL-only concurrency tests skipped under SQLite. The deployment wrapper repeats the full suite before restarting Gunicorn. No production records were used or changed during local validation.

Seven new tests cover shared language CSS, an actual CSRF-protected EN/BG language POST returning to the same hut route and query, retained authentication, Bulgarian primary hub/dashboard copy, cleaner permissions, hut isolation and existing decision form contracts. Existing dashboard assertions were updated to reference the new layout rather than obsolete CSS markers.

## Browser checks

- Desktop overview: compact header, four operational counts, pending decisions, capacity details, confirmed arrivals and monthly snapshot.
- English and Bulgarian dashboard/hub at 320 and 390 px phone widths: no page horizontal overflow; the language buttons have 44 × 44 px targets and a visible active language.
- Mobile navigation drawer opens; Escape closes it and restores focus.
- Pending approval expands the existing confirmation interface. No operational form was submitted from the visual preview.
- Four offline EN/BG HTML previews have embedded CSS, fonts and images, no external resource dependency, no CSRF tokens, and disconnected operational forms.

Functional language POST behavior was tested in Django; the separate static visual preview does not submit operational requests. Primary hut hub content is localized; detailed legacy report content is not comprehensively translated by this release.

## Release checks

- 48 installer and rollback checks passed across known v169, v170, v173, v174 and v175 source baselines: read-only preflight, installed hashes, unchanged unrelated files, idempotence, preserved modes, private backups and exact source rollback.
- Unknown customizations and prerequisite edits, damaged payloads, symlink targets and non-file targets were refused before source changes. An injected installation write failure restored the original source. Later source edits and modified backups prevented rollback.
- 22 production-environment checks passed, including the real installer preflight, installation and verification paths using the project's settings rather than staged settings.
- All 14 payload hashes match the verified application source; deployment and rollback shell syntax passed.

This package has not been installed on the live server by this session. The production installer prints the concrete backup path to use for rollback. No database migration is added.
