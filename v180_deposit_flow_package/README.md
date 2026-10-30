# v180 — Approval, deposit and confirmation

One cumulative upgrade from known v177, v178 or v179 application sources. Includes the previously prepared receipt and guest-portal updates. This package has not been deployed in this session.

## What changes

1. A guest submits a pending request. No payment is collected by the request form.
2. The manager opens **Approve**, checks capacity, reviews the required deposit, hut-local deadline and actual payment instructions, then approves. The request stays pending as **Awaiting deposit**, holding its beds.
3. The guest receives the amount, remaining deposit, deadline, payment reference, instructions and private status link. English/Bulgarian guest pages show the same fixed terms. The email is a payment request, not a confirmation.
4. In the reservation's payment record, the manager verifies that money was received and records it. Partial payments reduce the remainder. Net recorded funds reaching the required deposit automatically confirm the stay and queue a confirmation email with the remaining booking balance.
5. Insufficient recorded funds at the deadline release the hold. Core availability stops counting it at the deadline; the independent minute worker changes the stored status to cancelled and queues the expiry email. Late funds remain recorded but cannot automatically reopen the booking.

**This records payments already received; it does not charge a card or move bank funds.** A deadline refers to the deposit being recorded by the hut. Staff should reconcile incoming funds promptly. Expiry retains partial payments and does not initiate refunds.

Existing confirmed bookings are not enrolled or cancelled by this migration. Existing unreviewed guest requests enter the new flow when the manager approves them. Staff-created manual reservations retain their existing confirmation behavior.

## Deposit defaults and staff work

The existing per-hut Deposits settings supply the percentage and days after approval (fallback: 30% and three days). The initial deadline is capped at 23:59 on arrival day in `Europe/Sofia`; zero days means the end of the approval day. The approval form can change the amount and deadline. A positive outstanding deposit requires payment instructions in at least one language; the hut's saved EN/BG instructions prefill the form. Review these for real beneficiary/account/payment details before approving. A zero deposit is an explicit waiver and confirms without inventing a ledger payment.

Approved terms are stored separately and remain fixed when hut policies, instructions or room prices change. While an approved hold is unpaid or awaiting paid-capacity review, withdraw the approval with a reason before changing dates, rooms, beds or rates. Then approve new terms, using the existing ledger credit. The history is retained. Declining/cancelling closes the old request. Undo is guarded and cannot undo an approval after a payment has been recorded.

The dashboard separates requests needing a decision from deposit follow-up. The approval queue and reservation filters include approved holds. If full timely funds are recorded but a later room closure/capacity change prevents confirmation, the stay enters **Deposit received — staff review**. It is not confirmed and does not automatically expire. The guest is told to wait, assigned managers receive an alert, and the dashboard flags the review. Resolve availability, withdraw the old approval and approve again with the recorded credit.

The reminder is queued once before the deadline: halfway through a short hold or 24 hours before a longer one. Partial payments are reflected again at delivery. Paid, expired, withdrawn and superseded requests suppress stale payment emails. Existing email-import settings and SMTP credentials are retained. SMTP delivery is at least once; a crash after SMTP acceptance can still repeat an email. Signed payment form replay protection prevents a repeated click from adding a second ledger transaction.

## Preview

Open `previews/PREVIEW.html` after extracting the ZIP. It contains EN/BG examples of awaiting, partial, paid, waived, expired, paid-review and unreviewed bookings, plus receipt, dashboard, approval and payment screens. Bank details and guests are synthetic; operational submissions and links are disconnected. No preview data is installed.

## 1. Windows PowerShell — upload

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v180_deposit_flow.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu — preflight

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v180_deposit_flow.zip
python3 v180_deposit_flow_package/install_v180.py
```

In production this step validates/stages the package without replacing application source. Unknown relevant source edits, later/custom migration files, unsafe paths and corrupted payloads are refused before writes. No force-overwrite option is provided.

## 3. Ubuntu — deploy

```bash
bash v180_deposit_flow_package/deploy_v180.sh
```

The wrapper loads `/etc/hut-reservations/postgres.env`, uses `myprojectenv/bin/python`, stops Gunicorn and its socket, backs up the actual previous source, applies the additive migration and runs checks. It runs the isolated SQLite suite and then the full suite against a newly created, randomly named PostgreSQL test database. PostgreSQL verification uses `sudo -u postgres createdb/dropdb`; only the database created by that verification is removed. It never uses the live database as the test target and never changes the application database role/password. The test setting rejects names outside its dedicated temporary prefix. Normal sudo access to the local PostgreSQL account is needed for this step.

After tests, it collects static files, installs two separate systemd minute timers and starts the app. There is a maintenance interruption while this runs. If a required step fails, the wrapper leaves Gunicorn stopped and prints the error; fix that error and rerun the same deployment. Do not reverse the database migration to recover source. The migration is additive and does not backfill approvals, alter saved rates or delete payment records.

Press Ctrl+F5 after success. Check a real hut's payment instructions and the Deposits defaults, then use the approval/payment screens for normal work. Do not mark a deposit received without checking actual receipt of funds.

## Scheduled jobs

- `summitdesk-deposit-holds.timer`: releases due holds and queues reminders, without SMTP delivery.
- `summitdesk-deposit-mail.timer`: delivers/retries a bounded batch independently, so mail delays cannot block deadline releases.

Each service runs as `deploy`, loads the existing production environment through the provided bash runner, and uses the existing virtual environment. No external scheduling service is used. The services do not overlap themselves. SMTP failures remain visible in Email delivery and are retried up to the existing attempt limit.

Useful checks:

```bash
sudo systemctl list-timers 'summitdesk-deposit-*'
sudo journalctl -u summitdesk-deposit-holds.service -u summitdesk-deposit-mail.service -n 50 --no-pager
```

## Source rollback

Use the exact source-backup path printed by installation:

```bash
bash v180_deposit_flow_package/rollback_v180.sh summitdesk_backups/deposit_flow_v180_TIMESTAMP
```

Rollback refuses while unpaid approved holds or paid-review holds remain pending. Resolve or explicitly withdraw those approvals first; legacy source cannot manage their deadlines safely. It checks again after stopping writers. On a successful rollback it restores the actual prior source, disables the new timers, collects static assets and restarts Gunicorn. The additive migration file/schema, approval history and payment ledger are retained. No database reverse/drop migration is supplied. Later source edits or altered backups are refused.

## Validation

Local verification: 784 tests ran; 775 passed, nine PostgreSQL-only concurrency tests were skipped because this local environment has no PostgreSQL server. The three new PostgreSQL tests cover payment winning against expiry, expiry winning against late payment, and concurrent replay of one payment form. The deployment runs these on the separate PostgreSQL test database before reopening the app; they have not been run against your server in this session.

The new local integration tests cover positive/zero/prepaid approvals, fixed terms, validation recovery, private-link revocation, duplicate approvals/payments, partial/full/late funds, deadline capacity release, timely recorded funds reconciled later, reminder timing/remainder/staleness, SMTP outage/retry, paid capacity review, mutation/undo guards, manager scope/CSRF, nonstaff assigned-manager payment access, legacy preservation, checked-in exceptions, rollback refusal and Bulgarian guest screens. Existing confirmation tests now explicitly select a zero-deposit waiver where confirmation is their intended scenario. The old editor's direct confirmation test now verifies that the bypass is blocked.

33 installer/rollback checks passed across v177/v178/v179, including retained migration history, read-only preflight, modes, source integrity, idempotence, source restoration, unknown edits/migrations, symlinks and injected write failure. 23 production-environment checks passed. A forward migration trial retained legacy status, rates and ledger without backfilling holds, and verified that previous source can still read/write the additive schema. No migration drift was detected. Shell syntax and systemd unit verification passed. Browser QA used synthetic desktop and EN/BG mobile pages; the 390 px guest and 320 px staff payment pages had no horizontal overflow. No live guest link, real payment or production record was used.
