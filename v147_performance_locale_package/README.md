# SummitDesk v147 — calendar performance, Bulgarian booking and keyboard access

One cumulative upgrade ZIP for the uploaded source through v143, v145, v145.1 or v146. It includes the earlier guest-access, duplicate-request, email-retry, CSV-test, booking UI and superuser-admin fixes. Install this package directly; do not run an older installer afterwards.

## Changes

- Public monthly availability is calculated for the whole range in two inventory queries, instead of two queries for every day. A 30-day, hut-scoped request now uses 4 queries total instead of 62 on the synthetic fixture, with identical daily results. The global endpoint uses 3. No availability cache is introduced.
- The same holding statuses, checkout-exclusive dates, per-room zero floor, and overlapping physical-bed closure rules are preserved. Inactive huts and rooms are excluded from unscoped public availability. No guest information is returned by that endpoint.
- EN / БГ language controls on the public and staff headers. Selection uses Django's CSRF-protected language view, preserves the current page/query, and remembers the preference in the standard language cookie. A Bulgarian browser preference is recognized until an explicit choice overrides it.
- Bulgarian public home, hut directory, booking, reservation receipt, private-link recovery, guest portal, shared staff navigation and monthly stay planner. Form labels and the public date, group-size and availability errors are translated. The compiled translation catalog is included; no gettext installation is needed on the server.
- Dates and displayed decimal amounts follow the selected language. The monthly planner and older staff booking forms retain plain decimal values in `data-price` attributes, preventing comma-formatted prices from breaking calculations. Configured currency and stored prices remain unchanged; this is no currency conversion.
- Calendar date buttons use one Tab stop. Arrow keys move across dates/rooms; Page Up / Page Down move across date windows; Enter / Space select arrival/departure. Focus movement does not create a reservation. The selected departure is exposed as pressed, descriptions include keyboard instructions, and preview close returns focus to its trigger.
- Stronger focus outlines, localized quantity labels, associated form errors and mobile language controls. Existing approval, permission and server-side booking rules remain in force.

Translation scope is the public booking journey, shared navigation and monthly planner. Older reporting/operations screens and notification email bodies may still contain English; property names and manager-entered descriptions are kept as entered. Choose the language before entering a booking: a full-page language switch preserves query dates/group size but does not preserve unsent form fields. Date-availability refresh continues to preserve guest details.

## Install — the usual three steps

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v147_performance_locale.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v147_performance_locale.zip
python3 v147_performance_locale_package/install_v147.py
```

3. Deploy:

```bash
bash v147_performance_locale_package/deploy_v147.sh
```

The installer validates payload hashes and all known source versions before writing. It refuses unknown edits (including a customized `config/settings.py`) without changing source. It backs up the files it changes, uses atomic writes, and restores original files if installation encounters a write failure. Repeat installation is safe. No credentials, databases, virtual environments, unrelated backups or older ZIPs are bundled.

The deployment script requires every v147 source file to be installed, loads the existing `myprojectenv` and `/etc/hut-reservations/postgres.env`, creates a private database backup, applies pending migrations, checks the app, runs all tests against an isolated SQLite test database, collects static files, enables the existing v145 notification-retry timer and restarts Gunicorn. It stops on an error. Source deployment rollback remains manual; do not continue past a failed step.

There is no new v147 schema migration. The cumulative package retains additive v145 migration 0020 for servers upgrading from v143. Your existing environment-based database and SMTP credentials are used.

## Rollback

Find the exact source backup:

```bash
python3 v147_performance_locale_package/rollback_v147.py --list
```

Use the backup directory printed by the installer:

```bash
bash v147_performance_locale_package/rollback_v147.sh summitdesk_backups/performance_locale_v147_TIMESTAMP
```

The wrapper checks backup/source integrity, restores the previous files, collects static assets and restarts Gunicorn. Later source edits cause refusal. Reservation, payment and notification data are kept; additive migration history is retained. It is a source rollback, not a database restore. On failure, stop and save the error output.

## Post-deployment checks

1. Hard refresh with Ctrl+F5. Select EN, then БГ. Reopen a hut with dates and two guests; check room prices, the summary and the full total.
2. Enter guest details, then refresh the dates. Details should remain; an unavailable selection should be reduced with an explanation. Do not submit a real guest request just to test a page.
3. In the staff planner, use Tab to reach a date, arrows to explore, Page Down to move periods, then Enter to select arrival and departure. Check that departure is not charged.
4. Open and close a reservation preview using the keyboard. Focus should return to its preview button.
5. On mobile, check the language buttons, short calendar windows and booking-summary link.
6. Check that superusers see Hut, Room and Reservation in Django Admin; ordinary manager access stays scoped.
7. Check Email delivery for outstanding failures and the retry timer status. Email retries do not create bookings.

## Validation and limits

- 488 Django tests: 484 passed, 4 PostgreSQL-only concurrency checks skipped on SQLite.
- 83 DOM interaction assertions passed for English and Bulgarian public booking, desktop planner, mobile planner, keyboard navigation, full stay totals, date changes, conflicts, alternatives and preview focus restoration.
- Query comparison: the same 30-day fixture returned identical JSON with 62 queries in v146 and 4 in v147. New regression tests enforce query budgets, parity with `free_beds`, no stale cache, active-property scope, checkout and overlapping closures.
- System checks, JavaScript syntax, translation placeholder checks and migration drift checks pass.
- Installer checks cover all four supported source baselines, preflight, backups, repeated install, normal rollback, refusing unknown edits, detecting corrupted payload, recovering from an injected write failure, and protecting later edits. Deployment refuses incomplete source installation.

The isolated runtime has no working browser binary. DOM checks do not verify real layout, assistive technology or browser-native date controls. Live desktop/mobile rendering, real email delivery, PostgreSQL concurrency and this server deployment have not been verified here. A working domain is still needed for the live review.

Implementation references: Django's [translation](https://docs.djangoproject.com/en/6.1/topics/i18n/translation/), [format localization](https://docs.djangoproject.com/en/6.1/topics/i18n/formatting/) and [database optimization](https://docs.djangoproject.com/en/6.1/topics/db/optimization/) documentation.
