# v175 — Booking journey checks and reliable guest-review emails

The complete booking journey was exercised using synthetic guests, an isolated test database and captured in-memory email. One defect was reproduced and fixed: after a manager reviewed a guest's change/cancellation request, an SMTP failure silently discarded the guest's notification.

The review and its notification now commit together. The existing delivery queue attempts email after commit and retains failures for the normal retry controls. Repeated review submissions do not create another notification; different requests each have their own notification. Approving a guest change/cancellation request still requires a separate booking update by the manager.

The package changes only two application files: `bookings/self_service.py` and the new `bookings/test_booking_journey_v175.py`. No migration or automatic booking/data update is introduced. It preserves the installed homepage and booking interface. The known v169–v174 backend is supported; v174 does not need to be reinstalled.

## 1. Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v175_booking_reliability.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu: install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v175_booking_reliability.zip
python3 v175_booking_reliability_package/install_v175.py
```

## 3. Ubuntu: verify and deploy

```bash
bash v175_booking_reliability_package/deploy_v175.sh
```

The wrapper loads `/etc/hut-reservations/postgres.env`, uses `myprojectenv/bin/python` directly, verifies installed source, runs Django checks and the isolated regression suite, then restarts Gunicorn. Test emails use the in-memory backend. Some older regression tests intentionally simulate SMTP outages and may log “Reservation notification … could not be delivered”; the final test result must be `OK`.

## Check the production SMTP connection without sending email

```bash
bash v175_booking_reliability_package/check_email_v175.sh --connect
```

This diagnostic reads the effective Django email configuration and aggregate notification totals, then opens/authenticates and closes SMTP. It sends no messages, executes no retry job, changes no booking or queue record, and prints no account names, passwords, recipient addresses or private links.

Without `--connect`, only configuration and queue totals are checked:

```bash
bash v175_booking_reliability_package/check_email_v175.sh
```

A successful SMTP connection does not prove inbox delivery or spam-folder placement. Those still require a controlled live test with the intended recipients. The production connection, live inboxes and retry-worker schedule could not be inspected from the local workspace.

## Retry behaviour

New guest-review emails use the existing `ReservationNotification` queue as `change_review_guest`. The existing staff email-delivery screen and configured retry worker can retry them. This patch does not install or change a cron job. Previously discarded emails that never created a queue record are not reconstructed automatically.

## Rollback

Use the exact source backup path printed by installation:

```bash
bash v175_booking_reliability_package/rollback_v175.sh summitdesk_backups/booking_reliability_v175_TIMESTAMP
```

Replace `TIMESTAMP` with the actual printed timestamp. Source and backup integrity are checked before restoring the previous code and restarting the application. Booking data and already queued notifications remain.

See `BOOKING_JOURNEY_RESULTS.md` for the verified cases, defect and limitations.
