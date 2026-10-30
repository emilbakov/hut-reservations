# v189 — hut arrival information for guests

Requires v188 room galleries. Adds optional, hut-specific directions, parking, arrival notes and check-in/check-out times. All new fields start blank; no times, parking arrangements, directions or policies are guessed. Existing public hut phone, email and map link are reused.

## Deploy

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v189_arrival_info.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu, already connected:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v189_arrival_info.zip
python3 v189_arrival_info_package/install_v189.py
```

The production installer validates exact source hashes and settings without changing source. Unknown customizations or incompatible versions are refused. Do not force overwrite them.

3. Deploy:

```bash
bash v189_arrival_info_package/deploy_v189.sh
```

The wrapper uses the shared deployment lock, records/pauses previously active writers, verifies a private full PostgreSQL archive, backs up source, installs and applies additive migration 0034, runs Django checks and the SQLite plus isolated PostgreSQL suites, collects static files and resumes the original units. Gunicorn socket starts before service. Migration changes no bookings, rates, deposits, contact details, galleries or queued emails.

On failure, fix the reported error and rerun the same wrapper. Writers remain stopped and their original active state is retained for retry. Do not reverse migration 0034.

## Configure the actual information

Open **Settings > Arrival information** in the staff sidebar, or visit `/staff/arrival/`. The Guest communications screen also links there. Choose a permitted hut and fill only the facts you know:

- Actual public hut phone and email.
- Existing actual hut location/directions URL (HTTP/HTTPS).
- Optional check-in from, check-in until and check-out by times, in local hut time.
- Directions in English and Bulgarian.
- Parking instructions in English and Bulgarian.
- Arrival notes in English and Bulgarian, such as the actual procedure for late arrivals.

The page includes a guest preview. The same new fields are available under **Django admin > Huts > Arrival information**. Existing Public booking information contains phone/email/map fields.

Unknown fields remain hidden on the guest page. Supplying one language works: the page uses the selected language and falls back to the available text with the correct language marker. Times are informational; they do not change stay dates, availability, seasonal pricing or deposit deadlines. Saving this form sends no emails and changes no reservations or payment instructions.

Access is limited to assigned hut managers or superusers. Another hut's settings cannot be read or changed through a forged URL/POST. CSRF, phone/email/URL/time validation and text-length limits apply. Plain text is escaped on guest pages; maps are links, not third-party embedded widgets.

## Guest pages and email behavior

The reservation receipt and private guest portal show the hut's current arrival details, contact links and map. Call/email/map links have mobile-friendly touch targets. Cancelled or expired bookings keep contact details while arrival instructions are hidden. The homepage and booking prices are unchanged.

New confirmation emails include the arrival details, including when a hut uses a custom confirmation template. Existing pre-arrival messages include them too, preserving custom text. Arrival blocks use English and Bulgarian because the application does not persist a preferred guest email language. No new email job/timer is installed or scheduled; the existing pre-arrival workflow is used.

Pre-arrival messages are eligible only for confirmed stays two days before arrival. Pending requests and unpaid holds no longer receive the pre-arrival welcome message. Other payment/deposit workflows retain their current rules.

Already queued/sent emails are not rewritten or resent after a settings change. Existing guests immediately see updated facts on their private booking page. Confirmation deduplication and private-link separation between guest and manager copies remain intact.

## Source rollback

Use the exact source backup path printed during deployment, not the database archive folder:

```bash
bash v189_arrival_info_package/rollback_v189.sh summitdesk_backups/arrival_info_v189_TIMESTAMP
```

Replace TIMESTAMP with the actual printed source backup path. Rollback verifies current source/backup hashes, restores v188 source, checks and collects static files, then resumes the original units. Migration 0034 and saved arrival facts are retained; older ORM inserts remain compatible. Arrival facts will be hidden under older source until v189 is installed again. Existing email body text remains stored.

Gallery and seasonal-price records do not block this rollback because v188 supports them. No rooms, photos, bookings, payments or guest history are deleted. Source rollback does not restore a prior database state.

Private source backups: `summitdesk_backups/arrival_info_v189_TIMESTAMP/`.
Private database archives/checksums: `summitdesk_backups/arrival_info_v189_database_TIMESTAMP/`.
Backups may contain sensitive guest data. Database archives do not contain uploaded media files.

See VALIDATION.md for checks and local PostgreSQL limitations.
