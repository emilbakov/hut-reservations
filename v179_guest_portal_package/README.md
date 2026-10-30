# v179 — Guest stay manager and reservation pages

One upgrade from known v177 or v178 application sources. It includes the v178 reservation receipt/access redesign and adds the redesigned private guest page at `/guest/manage/<token>/`. The guest page opens from the email's private link or the receipt's change-request button.

## Guest-page changes

- The public cream, forest-green and serif styling now continues through the stay manager. Current hut, dates, guest, bed count and total appear together, with jump links to requests, messages and stay details.
- Change/cancellation requests use the existing field names and endpoints. Dates are required for a date change and ignored for a cancellation. All date errors appear together with a linked, focused summary. Failed validation retains notes and date values.
- An existing pending request replaces the new-request form with a review notice. The locked server check still prevents duplicate pending requests. Request history shows requested dates, the guest's details and the manager's note. Approval remains a manager decision and does not automatically change the reservation.
- Guest/team messages are easier to read. The existing reservation scoping, 2,000-character limit, five-message hourly cap, revocation and messaging window remain. Existing email-import and SMTP configuration are not changed. Interface labels, request statuses and guest feedback have Bulgarian translations.
- Saved room rates, booking totals and payment records remain separate. Cancelled stays show their original booking total and net payment record without presenting a deposit as still payable. No payment or refund is processed by this update.

The package also includes v178's read-only `/r/` guide, receipt layouts, recovery screen and print enhancement. Private links, CSRF protection, manager review and the no-store/noindex rules remain. The public homepage, main booking form, hut directory data, staff dashboard, inventory and payment ledger are not changed. Installation introduces no database migration and imports no preview records.

## Offline preview

Extract the ZIP and open `previews/PREVIEW.html`. It links to EN/BG guest pages with a normal stay, pending request, cancelled stay, closed messaging and validation errors. Receipt/access samples are included separately. All records, references, messages and contact details are synthetic. Forms and operational/external links are disconnected from your server. Fonts, styles, scripts and images are embedded. Preview records are never installed in the live database.

## 1. Windows PowerShell — upload

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v179_guest_portal.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu — install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v179_guest_portal.zip
python3 v179_guest_portal_package/install_v179.py
```

## 3. Ubuntu — test and deploy

```bash
bash v179_guest_portal_package/deploy_v179.sh
```

The wrapper loads `/etc/hut-reservations/postgres.env`, uses `myprojectenv/bin/python`, checks installed source, runs isolated tests, collects static files and restarts Gunicorn. Press Ctrl+F5 after success. Open your own private guest link and check requests and messages. The `/r/` landing page and receipts are included in the upgrade.

The installer accepts known v177/v178 source hashes and the known pre-v175 self-service file when accompanied by the matching notification prerequisite. In that case the already-authorized reliable review-notification code is retained as part of the new self-service file. Unknown relevant edits are refused before writes. Existing file modes are preserved and a private source backup is created.

## Rollback

Use the exact source-backup path printed by installation:

```bash
bash v179_guest_portal_package/rollback_v179.sh summitdesk_backups/guest_portal_v179_TIMESTAMP
```

Replace `TIMESTAMP` with the printed value. Rollback checks installed source and backup integrity, restores your actual prior source, collects static assets and restarts Gunicorn. From a v178 installation, the v178 receipt layout remains after rollback. No booking, request, message or payment records are deleted.

## Validation

746 tests ran in 13.710 seconds: 740 passed, 6 PostgreSQL-only concurrency tests skipped under SQLite. Seven new regression tests cover bound error recovery and successful resubmission without booking mutation; combined date/detail errors; cancellation date handling and duplicate pending requests; CSRF, revocation and stay cutoffs; Bulgarian switching and guest receipt access; saved rates/payment arithmetic/cancelled wording; and escaped, reservation-scoped history/messages.

24 installer/rollback checks passed across v177 and v178, including read-only preflight, installed hashes, modes, idempotence, exact rollback, unknown edits, corrupted payloads, symlinks, injected write failure and protection for later edits/changed backups. 22 production-environment checks passed using the actual installed settings rather than staged settings.

Browser QA used synthetic records: desktop and 390 px Bulgarian layouts; 320 px Bulgarian error state; no horizontal page overflow; 44 px language/navigation targets; cancellation hides/disables dates; reversed dates are blocked and correcting arrival clears the departure error; failed validation focuses the two-error summary and retains the note. Operational requests were tested in Django's isolated database, not submitted through the static visual preview. No live guest link or production data was used. This session has not deployed the package.
