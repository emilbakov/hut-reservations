# v181 — Deposits dashboard

Upgrade for known original or repaired v180 application source. This package has not been deployed in this session. It adds no migration and does not backfill, confirm, cancel, charge or refund reservations when the dashboard is opened.

## Staff workflow

Open `/staff/deposits/`. The compact header and four counters show awaiting deposits, deadlines within 24 hours, partial payments and records needing review. Hut/search filters and deposit defaults are collapsed initially. A single-column list shows the guest/reference, stay, deposit target, net recorded funds, outstanding deposit, exact deadline and available reminder status. Amounts use the saved approved deposit terms, not a new percentage calculation.

- **Needs attention:** unpaid active deposits, overdue holds waiting for the deadline worker, and records requiring review.
- **Awaiting deposit / Due within 24 hours / Partial payments:** overlapping filters describing current outstanding deposits. The partial amount is net payments after recorded refunds.
- **Overdue:** deadlines passed for holds still waiting for the worker, and overdue legacy deposits. Elapsed v180 holds do not offer a new-payment shortcut or display a payable remainder. The page does not run expiry; the existing minute worker handles the transition.
- **Needs review:** expired/cancelled bookings with recorded funds, paid room-capacity reviews, unusual negative balances, paid deposits subsequently below their requirement, pre-approval credit, and checked-in overdue holds. This is a review flag, not a refund decision. Existing immutable cancellation settlements resolve a record when their retained balance still matches and no newer ledger activity exists. Later activity brings it back into review.
- **Deposit met / Closed / Legacy policy / All records:** keep fully funded, waived and closed records accessible. Legacy confirmed/manual bookings retain the existing policy calculation and are marked explicitly. They are not automatically enrolled into v180 expiry.

Unapproved guest requests without recorded funds stay in the approval queue. Historical multi-hut bookings are omitted from this single-hut payment dashboard. Hut scope is checked against every item; another hut's guest/payment details are not exposed through counts, search or rows. Superusers may select all huts, but multi-hut records remain omitted.

Record received payment opens the existing scoped ledger form, with its existing CSRF, receipt-verification guidance and signed duplicate-submission guard. Payment history links directly to the history section. The dashboard does not introduce inline payment/refund writes. Policy POST remains the existing validated, hut-scoped, CSRF-protected action; saving it keeps the selected hut. Approved terms and saved reminder preference remain fixed, while legacy settings retain their prior behavior.

Counts reflect the selected hut and search across statuses. Results have 25 records per page; search, hut and status survive pagination. The page does not silently discard matches after 200 records. Related data is prefetched so query count does not grow once per displayed booking. Interface labels are available in English and Bulgarian. Mobile cards, locally hosted fonts, visible focus and at least 44 px action targets follow the staff dashboard styling.

## One upgrade

The corrected booking replay test is included even when the original v180 test file is installed. The new deployment and rollback wrappers start `gunicorn.socket` before `gunicorn.service` when the socket exists. Separate repair ZIPs are not required for v181. Existing v180 deadline and mail jobs remain in use and are restarted after verification. Source/configuration prerequisites are checked before application writes.

## 1. Windows PowerShell — upload

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v181_deposit_dashboard.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu — preflight

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v181_deposit_dashboard.zip
python3 v181_deposit_dashboard_package/install_v181.py
```

Production installation at this step validates without changing live source. It uses the actual installed settings for environment checks, requires the v180 source prerequisites, checks payload/source hashes, refuses unknown edits and unsafe paths, and preserves actual prior file modes. No production setting or credential is supplied/replaced by this upgrade.

## 3. Ubuntu — deploy

```bash
bash v181_deposit_dashboard_package/deploy_v181.sh
```

The wrapper loads `/etc/hut-reservations/postgres.env` and uses `myprojectenv/bin/python`. It checks that existing migrations are applied and both v180 timer units exist before stopping the app. It then pauses Gunicorn and deposit jobs, creates a private source backup, applies/verifies the source and runs Django checks plus the isolated SQLite and PostgreSQL suites. PostgreSQL verification creates/removes only its own randomly named test database through `sudo -u postgres`. There is a short maintenance interruption. No new migration is applied.

After tests, it collects static files, starts the socket before Gunicorn and resumes the existing timers. If a required step fails, Gunicorn remains stopped; fix the reported error and rerun this same deployment. The backup path is printed by installation. Do not bypass failed tests or reverse database migrations for this UI update.

After success, hard refresh with Ctrl+F5 and open `/staff/deposits/`. Check the hut selector, partial/review filters, a payment-history link and Bulgarian/mobile layout. No live payment needs to be invented to review the page.

## Offline previews

Extract the ZIP and open `previews/PREVIEW.html`. English/Bulgarian examples cover attention, review, partial, received, closed and all records. Keep the adjacent `static` folder with the pages. Names, references, emails and amounts are synthetic. Forms and operational/server links are disconnected. The previews do not connect to the live application or import any data into it.

## Source rollback

Use the exact backup path printed during deployment:

```bash
bash v181_deposit_dashboard_package/rollback_v181.sh summitdesk_backups/deposit_dashboard_v181_TIMESTAMP
```

The wrapper verifies source/backup integrity, pauses the app/jobs, restores the actual prior v180 source, checks and collects assets, starts the socket before Gunicorn and resumes the deposit timers. Later source edits or altered backups are refused. It does not reverse schema or delete/change approval, booking or ledger records. Active v180 approved holds can remain because the previous source still supports the v180 lifecycle. This differs from rolling all the way back to pre-v180 code.

## Validation

801 tests ran locally: 792 passed and nine PostgreSQL-only tests skipped because the local environment has no PostgreSQL server. The deployment runs the PostgreSQL suite against its isolated test database before reopening the app. The final 16-test dashboard suite also passed after copy/layout refinements.

New regressions cover immutable terms under policy changes; overlapping status counters; partial/refund math; expired positive balances and paid capacity review; closed/refunded/retained settlements and later funds; unapproved credit without invented terms; legacy policy; all-item hut isolation; search/count/pagination consistency beyond 25 rows; exact elapsed deadlines without requesting payment; zero GET lifecycle/ledger/email writes; payment/history destinations and form token; policy scope/CSRF; staff authorization; escaped names; checked-in overdue exceptions; Bulgarian reminders; and bounded query growth.

24 installer/rollback checks passed across original and replay-repaired v180 source, including read-only preflight, idempotence, source integrity, modes, exact source restoration, unknown edits, corrupted payload, symlinks, injected write failure and altered backups. 23 production-environment checks passed. No migration drift was detected and shell syntax checks passed. The wrappers retain the tested socket-first/no-socket startup pattern from the startup repair.

Browser QA used synthetic desktop and 320 px Bulgarian pages, checked the collapsed/expanded filters and verified no horizontal document overflow. Payment actions were verified through Django's isolated test client; no real guest link or production ledger was used. No deployment to your server was performed from this session.
