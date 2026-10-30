# v169 validation

- Full Django suite: 709 tests ran in 12.736 seconds; 703 passed, 6 PostgreSQL-only tests skipped under SQLite. No failures.
- Migration drift check: no changes detected.
- 26 English/Bulgarian JavaScript checks passed with six gallery photographs: progressive links, tabs, keyboard navigation, cycling, focus restoration and mobile menu Escape.
- Both language renders checked for all timeline dates, historic labels, all 41 new Bulgarian translations, the unchanged booking route, and six photo viewer entries.
- Uploaded retro-043.jpg and the deployed image are byte-for-byte identical. Its frame, caption and archives.bg mark are retained; no date is invented.
- Browser QA: desktop history layout; Bulgarian mobile at 320 px, 390 px and 768 px with no horizontal overflow; native source disclosure; source-link targets at least 44 px high; new postcard opens in the viewer as photograph 4 of 6 and Escape returns to the page.
- 17 installer safety checks passed, including unknown edits, payload corruption, symlinks, write-failure recovery, exact rollback and preservation of the uploaded Admin.
- 22 production environment checks passed, including the actual installer check/install/verify paths with no config/settings.py staged in the payload. The checker reads the real project settings.
- Additional v153.1 -> v169 and v168 -> v169 checks passed: read-only preflight, install, exact final-source comparison, installed verification, rollback preflight and exact original-source restoration.
- The installer also accepts the exact uploaded v167 baseline, exercised by the installer checks. Financial prerequisites and the current migration chain remain guarded.

No production deployment or live PostgreSQL row-lock test was performed here. The deployment script runs its checks and isolated tests again before backing up the database, migrating, collecting static assets and restarting Gunicorn on the server.
