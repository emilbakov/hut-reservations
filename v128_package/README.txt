SummitDesk v128 — Guest Request Priorities and CSV Export
========================================================

Compatibility: Existing SummitDesk v127 with public guest request approvals.
The uploaded project already contains v127. This ZIP upgrades that checkout.

New manager features at /staff/reservations/requests/
  - Priority counts and filters: waiting over 24 hours; arrival due within
    two calendar days or already overdue (pending requests only).
  - Badges on urgent request cards.
  - Export all matching requests to CSV, not just the current page.
  - Export includes reference, status, guest contact, hut, rooms, stay dates,
    bed count, estimated total, guest notes, and waiting hours.
  - Same authorized hut and status/search/priority filters for screen/export.
  - Formula-injection protection for spreadsheet applications.
  - Exports are private/no-store and contain personal data: handle carefully.

Existing reservation approval/decline actions, availability rules, email
notifications, manager permissions, and database schema are unchanged.
No migrations or database changes are required.

INSTALL (on a v127 project, from the directory containing manage.py)
  1. Back up your live database and project code. Keep the backups private.
  2. Extract summitdesk_v128.zip into the project directory so you have
     v128_package/install_v128.py (no existing project files are overwritten
     by extracting this ZIP).
  3. Activate the project's existing virtual environment and production
     environment variables.
  4. Run:
        python v128_package/install_v128.py
        python manage.py check
        python manage.py test bookings.test_request_operations_v128 \
          bookings.test_approval_dashboard_v127 \
          bookings.test_guest_approval_v126 \
          bookings.test_reservation_management
        python manage.py test
  5. If all checks pass, restart your Django service (e.g. your Gunicorn
     systemd unit), and open /staff/reservations/requests/.

The installer performs preflight checks, creates a timestamped backup in
summitdesk_backups/request_operations_<timestamp>/, and writes atomically.
It refuses to run twice or on an incompatible v127 checkout. If the installer
reports an unexpected source layout, STOP and do not force the patch.

ROLLBACK (source files only; if not modified since installation)
  python v128_package/rollback_v128.py \
    summitdesk_backups/request_operations_<timestamp>

The rollback refuses to overwrite files changed after v128 installation.
Restart your service only after checking the restored code. There is no
schema migration to reverse.

Security: CSV contains guest personal information. Do not put it in public
web directories, share it publicly, or store it unencrypted. The export
never includes private guest portal links or access tokens.

Verification on an isolated copy of the uploaded project:
  - python manage.py check: passed
  - 56 targeted tests (v128, v127, v126, manager access): passed
  - Full suite: 295 tests passed (3 skipped)
  - makemigrations --check --dry-run: no changes detected
  - Installer and rollback verified on an isolated project copy
  - See the accompanying START_HERE.txt for quick steps.
