# SummitDesk v145 — booking reliability

This upgrade bundles the high-priority fixes from the review of your uploaded snapshot. That snapshot contains installed code through v143. v144 is not required.

## What changes

- A booking reference alone cannot reveal private details or authorize changes. Old email links open a recovery page that emails the current private link to the stored guest address. Recovery sends are limited to one notification per reservation per 15-minute window across workers.
- Revocation also blocks browser access established during booking. Recovery and notification retries never silently reactivate revoked access. Only a manager's explicit Reissue action restores it.
- Guests request changes and cancellations through the manager-review portal. They cannot bypass review through older modification/cancellation URLs. Authorized managers retain their existing tools.
- Public forms have a browser-bound submission token. Replaying the same form returns the original reservation, even after the last available bed was taken. Older forms without a token receive ten-minute duplicate protection within the same browser. Opening and submitting a new form remains a separate booking intention.
- Receipt, manager-request, approval and decline notifications have durable delivery records committed with the reservation/decision. A failed email does not lose the booking. Retries do not create reservations or repeat a successful delivery record.
- Guest approvals show failed-notification warnings. The new **Email delivery** screen shows status and allows property-authorized managers to retry. Message bodies and private tokens are hidden from this screen.
- Guests see a delay notice if their email delivery fails. Old pending-request notices become unnecessary when a manager has already approved or declined the booking.
- A systemd timer retries due notifications every five minutes. Automatic delivery is limited to five attempts with backoff. Managers can explicitly retry after that limit. Notification records marked Sent or Not needed are not resent.

The migration adds delivery/idempotency tables. It does not change existing reservation dates, quantities, payment records or approval statuses. Existing guest requests are not automatically expired. Historical email failures that predate this upgrade cannot be reconstructed automatically.

## Install in three steps

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v145_reliability.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v145_reliability.zip
python3 v145_reliability_package/install_v145.py
```

The installer checks every changed file against this snapshot before writing anything. It refuses unexpected/customized files, validates payload hashes and Python syntax, and makes a timestamped source backup. A repeated installation is safe. `--check` performs a read-only preflight.

3. Ubuntu:

```bash
bash v145_reliability_package/deploy_v145.sh
```

This activates `myprojectenv`, loads `/etc/hut-reservations/postgres.env`, selects `config.settings_postgres`, makes a private database backup, runs the migration and checks, runs the regression suite against an isolated in-memory SQLite database, collects static assets, enables the notification retry timer, and restarts/checks `gunicorn.service`.

It requires the existing deployment paths, a working PostgreSQL connection, `pg_dump`, and sudo for systemd. A backup or check failure stops the deployment script. Use the source rollback below if deployment cannot complete. The PostgreSQL dump is saved outside the project under `/home/deploy/reservation-backups/` with mode 600. No database credentials are included in this package or printed by the backup helper.

The service uses your existing SMTP environment. For Gmail, the existing environment must include `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `DJANGO_EMAIL_USER`, and `DJANGO_EMAIL_APP_PASSWORD`. This upgrade does not edit credentials. Console, dummy, and file-only backends are recorded as failed delivery in production instead of claiming an email was sent.

## Verify after deployment

Open Guest approvals or Email delivery. Make a test request using an address you control, then check that it remains pending, that guest and manager notices have the expected delivery status, and that the emailed private link works. A manager must approve the request before it becomes confirmed.

Check the timer if needed:

```bash
sudo systemctl status summitdesk-notification-retry-v145.timer --no-pager
```

Inspect due notifications without sending:

```bash
python manage.py retry_reservation_notifications --settings=config.settings_postgres
```

## Rollback

First stop the new retry timer and any running retry process:

```bash
sudo systemctl disable --now summitdesk-notification-retry-v145.timer
sudo systemctl stop summitdesk-notification-retry-v145.service
python3 v145_reliability_package/rollback_v145.py --list
```

Use the exact backup path printed by the installer/list command:

```bash
python3 v145_reliability_package/rollback_v145.py --check summitdesk_backups/reliability_v145_TIMESTAMP
python3 v145_reliability_package/rollback_v145.py summitdesk_backups/reliability_v145_TIMESTAMP
sudo systemctl restart gunicorn.service
```

Rollback refuses files edited after installation and verifies the backup's hashes. It restores the previous source without deleting reservations or delivery records. Additive database tables and migration 0020 are intentionally retained; do not reverse the migration or restore the entire database merely to revert source. Rolling back also restores the previous guest-access behaviour.

## Validation

- Full suite: **463 tests; 459 passed; 4 skipped** on Django 6.1.2 with isolated SQLite and in-memory email.
- 35 new regression tests cover revocation, recovery, review-only guest actions, duplicate requests, atomic delivery records, SMTP failures, retry limits, status warnings, token rotation, CSRF and property isolation.
- The four skipped tests require PostgreSQL, including the new concurrent replay/last-bed test. Run them in an isolated PostgreSQL test environment before treating concurrency as verified on your production database.
- Django system checks passed; no missing model migrations were detected.
- Installer checks passed: read-only preflight, installation, repeated installation, exact payload hashes, customized-file refusal, rollback edit protection, exact restoration, and automatic restoration after an injected write failure.
- The database backup helper was tested with a disposable SQLite database and private output permissions. The PostgreSQL `pg_dump` path and systemd activation must be verified on your Ubuntu server.
- Shell syntax and packaged Python compilation passed. No real Gmail delivery or live browser testing was performed here.

SMTP delivery is at least once: a process failure after SMTP acceptance but before recording success can rarely result in a repeated email. Inventory creation is protected separately by the database-backed submission record.

No changes have been deployed to your server by creating this ZIP.
