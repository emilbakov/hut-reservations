# v153 verification

- Full Django suite: **590 tests; 586 passed, 4 PostgreSQL-only tests skipped**, no failures. Nineteen new main-hut tests cover root rendering/submission/CSRF, canonical/form URLs, information-only hut pages, direct POST and legacy-form bypasses, forged foreign-room fields, directory privacy, scoped public availability, stale pages and the final transactional policy check, retired/deleted main huts, Admin validation, unconfigured/multiple/sole huts, existing secondary-hut staff approvals and Bulgarian notices. One new login test verifies that the unavailable response renders with zero branding database queries.
- **234 existing DOM interaction assertions passed:** 84 public/planner, 68 guest feedback/receipt, and 82 EN/BG staff checks. Date refresh, totals, retained details, error focus, private receipts, staff filters, decisions and the mobile calendar remain covered.
- **41 branding checks passed:** exact source PNG bytes, exact embedded favicon bytes, logo/icons on public/staff/Admin pages, visible names, explicit dimensions, information-only pages and escaped custom brand names.
- **11 main-hut selector checks passed**, including a real terminal input path, no guessing between multiple huts, exact-slug selection, inactive huts, idempotence and preservation of operator contact/brand settings.
- **66 installer safety checks passed** across 10 supported baselines: v143, v145/145.1, v146, v147, v148, v149, v150, v151 and v152. Includes verification/preflight, no-write checks, installation, idempotence, rollback, custom edits, damaged payload, injected write/deletion failures, later-edit protection and non-file targets.
- **23 media/environment checks passed.** No additional dependency is required. Deploy and rollback use the existing virtualenv interpreter directly.
- Temporary file-backed SQLite concurrency checks: eight login attempts admitted five password checks and rejected three in advance; eight booking quota requests competing for three slots admitted exactly three; four Undo requests plus four new bookings competing for one released bed left exactly one active hold.
- Migration check reports no pending changes beyond additive 0025. Packaging checks Python parsing, all project/app templates, source/payload hashes, static collection, required logo/font assets, shell syntax and ZIP CRC.

## Intentional regression updates

Presentation tests now expect Карлък and the main hut page at `/`. Multi-hut public tests explicitly select their intended main hut. Directory tests retain name/location filtering and now verify the information-only behavior; capacity checks run on the main page. Public JSON remains bounded at four queries including the main-hut policy lookup. A foreign hut's JSON availability is deliberately no longer public.

## Limits

DOM and template checks do not establish browser pixel layout, exact fold heights or device icon appearance. No local browser executable was available. No live-server requests, production bookings, screenshots, credential entry or deployment were performed. PostgreSQL concurrency was not run locally and the four inherited PostgreSQL-only tests remain skipped.
