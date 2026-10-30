# v182 — clear all reservation data

This is a one-off maintenance package for the existing v180/v181 PostgreSQL site. It installs no source files and changes no schema. It has not been run on your server.

**Scope: ALL huts, ALL reservation dates and statuses. Linked payment/deposit and refund ledgers, approved terms, cancellation settlements, room/bed allocations, check-in records, guest links, change requests, conversations, email queues, reminder/digest logs, booking submission tokens, reservation audit/admin history and reservation-linked cleaning events are removed. Old guest reservation links stop working.**

Huts, rooms, beds, floor plans, photos, staff/users and memberships, website/contact/history settings, deposit policies, message templates, expenses, bed closures, standalone cleaning events/readiness/tasks, login/rate protection and the email import cursor are retained. Gmail messages and previously delivered emails are not changed. Financial income associated with the deleted reservations disappears from reports; operational expenses stay.

IDs/sequences are kept increasing. Starting from zero means no reservations or reservation transactions, rather than reusing old IDs.

## 1. Upload — Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v182_reservation_reset.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Extract and preview — Ubuntu

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v182_reservation_reset.zip
bash v182_reservation_reset_package/reset_v182.sh --preview
```

The preview makes no changes and prints counts, not names or email addresses. PostgreSQL client tools `pg_dump` and `pg_restore` must be installed. Missing tables, unapplied migrations or unknown foreign-key relationships refuse the reset. Do not bypass those checks; share the exact error if one appears.

## 3. Clear the reservations

```bash
bash v182_reservation_reset_package/reset_v182.sh --execute
```

This is the destructive command. It:

1. Takes the existing deployment lock and repeats the preview.
2. Temporarily pauses Gunicorn, project systemd jobs and cron. Existing unmanaged application workers cause refusal rather than being killed.
3. Locks database tables against writes, creates a FULL PostgreSQL custom-format backup, checks the archive listing, and records its checksum and pre-reset counts.
4. Removes only the declared data in one database transaction, bypassing booking email/audit hooks, then checks the remaining counts and foreign-key constraints. It does not send cancellation or payment emails.
5. Restarts only the services/timers which were active before maintenance, with the Gunicorn socket before its service. Cron is resumed if it was previously active.

The website is briefly unavailable during maintenance. The private backup is printed as:

`/home/deploy/hut-reservations/summitdesk_backups/reservation_reset_v182_TIMESTAMP`

It contains guest/payment data and the full database, including staff password hashes. Keep it private. Nothing is uploaded off the server. If backup creation/validation or deletion fails, the deletion transaction rolls back; a completed backup is retained. Database connection/lock timeouts stop the operation instead of continuing without a backup. If a service fails to restart, the script reports it; that does not mean a committed reset was undone.

After success, hard refresh the dashboard, Reservations and Deposits. They should have no reservations. Create one fresh request using your own email and follow its approval/deposit flow. Bed closures and manual cleaning states still apply to availability.

## Restore the database if needed

Use the exact backup directory printed by the reset:

```bash
bash v182_reservation_reset_package/reset_v182.sh --restore /home/deploy/hut-reservations/summitdesk_backups/reservation_reset_v182_TIMESTAMP
```

This restores the **FULL database**, replacing ALL database changes since that backup, including new bookings and unrelated edits. It stops the same writers and restores with `pg_restore --single-transaction --exit-on-error`. The archive checksum, database/server/role identity and applied migration list must match. A corrupted, foreign or older-schema backup is refused. Application source and media files were not changed by the reset and are not restored.

## Validation

- 13 synthetic SQLite database tests: protected holds and partial payments, all huts/statuses, preserved configuration/expenses/users, no mail, preview, failure rollback, fresh booking, unknown relation refusal, backup failure/corruption, backup permissions/checksum and restore guards.
- 7 simulated systemd maintenance scenarios: socket/service order, service-only setup, reset failure, unmanaged worker refusal, inventory failure, preview and restore, with original active/inactive states preserved.
- Python compilation and Bash syntax checked.
- Actual PostgreSQL archive/restore was not run locally: this environment has no PostgreSQL client/server. On the server the real archive must succeed and pass `pg_restore --list` before any rows can be deleted. A listing/checksum verifies the archive format and bytes; it is not a trial restore.

The synthetic tests are included in `tests/` for review. They do not run against production. There is no source installer, migration, collectstatic or v181 deployment step in this package.
