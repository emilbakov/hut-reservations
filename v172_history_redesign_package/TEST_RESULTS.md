# v172 validation

- Django regression suite: 709 tests run in 12.084 seconds; 703 passed and 6 PostgreSQL-only tests skipped in the local SQLite test environment.
- Installer: 17 existing safety checks passed, including rejecting customized source, changed backup files and later edits, preserving source modes, and restoring source after an injected write failure.
- Production configuration: 22 existing environment checks passed, including the actual install and verification paths without a staged settings file.
- Exact install, verification and rollback passed from seven source states: uploaded v167, v153.1, v168, v169, v170, v171, and source obtained by installing v171 over v170 and then running its actual rollback.
- Both Bulgarian and English homepages render through Django. All referenced local static assets resolve. `/book/` renders successfully in both languages.
- DOM and existing gallery-script checks verified the two visible history photographs, three milestones, 2021 copy, removal of 1977/2019/historical notes, unique IDs, valid anchor destinations, six unique viewer images, opening either history photo, cycling images, focus return and mobile-menu link behaviour.
- The Bulgarian story section contains about 90 words, including captions and date labels.
- Existing v170 booking, backend, staff and financial source files are byte-identical. Homepage templates and translation catalogs are the only changed pre-existing files since v170; versioned history/gallery assets are additive.
- Shell syntax and all 58 package payload hashes were checked. The final ZIP is checked for CRC and exact payload bytes before delivery.

Validation used Django, its test client and JSDOM. A real-browser visual review could not be completed because the cloud browser could not reach the local preview server. Responsive layout should be visually checked after installation. No production server deployment was performed from this workspace.
