SummitDesk v129 — Daily Manager Guest Request Digests
====================================================

Compatibility: v128 already installed in /home/deploy/hut-reservations.
Adds a daily manager-only email digest for pending PUBLIC guest reservation
requests (guest_request=True). This is NOT a guest change/cancellation digest.

FEATURES
  - One digest per active manager per local calendar day (Europe/Sofia).
  - One email for a manager assigned to several active huts, grouped by hut.
  - Total pending requests, >24-hour waiting counts, arrival due within two
    days / overdue counts, and direct hut-filtered approval dashboard links.
  - Includes only requests that belong to exactly one authorized active hut.
  - No guest names, emails, phone numbers, tokens or other private links.
  - Preview-only by default. --send is opt-in and requires HTTPS base URL
    and a configured, non-console/non-dummy mail backend.
  - Durable per-manager/day database deduplication (new migration 0014).
  - No reservation status, payment, or bed availability changes.
  - Email delivery failures are reported and can be retried. SMTP success
    followed by a rare database-commit failure can still produce a duplicate
    on retry, because SMTP and database transactions are not atomic together.

STEP 1 — Windows PowerShell (save ZIP in Downloads first)
  scp "$env:USERPROFILE\Downloads\summitdesk_v129.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

STEP 2 — Ubuntu installation (BACK UP YOUR DATABASE AND PROJECT FIRST)
  ssh deploy@167.233.96.3
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v129.zip
  python3 v129_package/install_v129.py

STEP 3 — Production environment, migration and tests
  source myprojectenv/bin/activate
  export DJANGO_SETTINGS_MODULE=config.settings_postgres
  set -a; source /etc/hut-reservations/postgres.env; set +a

  python manage.py migrate --noinput
  python manage.py check
  python manage.py test bookings.test_manager_digest_v129 bookings.test_request_operations_v128 bookings.test_approval_dashboard_v127 bookings.test_guest_approval_v126
  python manage.py test bookings.test_manual_booking bookings.tests
  python manage.py test

After all tests pass, restart your actual Django service if needed.
The installer does NOT enable or start email delivery automatically.

PREVIEW (safe; does not send emails or create digest logs)
  python manage.py send_manager_request_digest
  python manage.py send_manager_request_digest --manager-id 123

ONE-TIME SMTP AND TIMER SETUP (requires sudo; choose your own real domain)
  1. Copy v129_package/manager-digest.env.example to
       /etc/hut-reservations/manager-digest.env
     and edit all placeholders: real HTTPS SUMMITDESK_BASE_URL, SMTP host,
     port, username, password, TLS/SSL, sender address.
     Keep the file private (root:root, chmod 600).
     The settings module reads DJANGO_EMAIL_* variables at runtime.
     Do not paste SMTP passwords into chat or logs.

  2. Install the included systemd units:
       sudo cp v129_package/units/summitdesk-manager-digest.service /etc/systemd/system/
       sudo cp v129_package/units/summitdesk-manager-digest.timer /etc/systemd/system/
       sudo systemctl daemon-reload

  3. Check the configuration and manually trigger ONE real delivery:
       sudo systemctl start summitdesk-manager-digest.service
       sudo journalctl -u summitdesk-manager-digest.service -n 40 --no-pager
     This immediately emails all eligible managers with pending requests.
     Re-running on the same Sofia calendar day skips already-sent managers.
     If SMTP fails, fix it and retry; the command exits nonzero.

  4. After verifying delivery, enable the timer:
       sudo systemctl enable --now summitdesk-manager-digest.timer
       sudo systemctl list-timers --all | grep summitdesk-manager-digest

     The timer runs at 08:00 Europe/Sofia daily, including DST changes.
     Persistent=true means a missed timer run can execute after reboot.
     To disable it:
       sudo systemctl disable --now summitdesk-manager-digest.timer

IMPORTANT
  - No cron job is created by the installer; enable the timer only once.
  - Verify SMTP credentials and a real HTTPS domain before --send.
  - The timer service runs as 'deploy', uses your existing PostgreSQL
    EnvironmentFile, and your myprojectenv Python interpreter.
  - Ensure /etc/hut-reservations/postgres.env is in systemd EnvironmentFile
    KEY=VALUE syntax (not shell commands like 'export' or 'source').
  - Back up production database before migrating. Migration 0014 only
    creates the ManagerRequestDigestLog table.

ROLLBACK
  Disable the timer first, then (after backing up the database) reverse
  migration 0014 only if no later migration depends on it:
    python manage.py migrate bookings 0013 --noinput
  Restore original source files with the backup path printed by installer:
    python3 v129_package/rollback_v129.py summitdesk_backups/manager_digest_<timestamp>
  This refuses to overwrite files modified since v129 installation.
  Review migration dependencies before rollback on a later version.

VERIFICATION
  See v129_package/TEST_RESULTS.txt for the exact isolated checks.
