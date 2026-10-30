# v178 — Private reservation pages

Requires the deployed v177 source. This update brings the reservation receipt and private-link access screens into the cream, forest green and serif style of the current public site.

- `/r/` becomes a read-only private-link guide. It does not look up bookings or accept an email address/reference. Guests follow the private link in their reservation email.
- `/r/<reference>/` retains the existing access checks. Authorized guests and hut staff see a redesigned receipt; everyone else sees the recovery screen without guest or room details.
- Pending, confirmed and cancelled stays have distinct wording. Pending totals are estimates; cancelled stays show the original booking total. The room breakdown uses the reservation's saved rates and totals, rather than current room prices.
- Dates, hut identity, guest details, payment instructions, hut contacts and next steps remain. Email-delivery delay warnings remain visible. Missing payment/reply instructions retain their existing honest fallback text.
- Guests continue to request reviewed changes/cancellations before their stay starts. Authorized staff retain direct edit/cancel tools, with a native inline cancellation confirmation instead of the browser popup. Cancellation does not process refunds.
- A print button enhances the receipt when JavaScript is available. Operational forms and the receipt work without it. Styles/fonts are local; English and Bulgarian interface text is included.

No migration, booking update, email send or production data import runs during installation. The main homepage, booking flow, hut directory content and staff dashboard are preserved. The v177 public base receives only an empty optional head block used by the new receipt base.

## Offline previews

Extract the ZIP and open `previews/PREVIEW.html`. It links to EN/BG versions of the entry guide, pending receipt, confirmed receipt, cancelled receipt, started stay, recovery screen and staff receipt. All records, references and contact details are synthetic. These records are never installed on the server. Assets are embedded; booking/recovery forms and operational/external navigation are disconnected. Print remains available.

## 1. Windows PowerShell — upload

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v178_reservation_redesign.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu — install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v178_reservation_redesign.zip
python3 v178_reservation_redesign_package/install_v178.py
```

## 3. Ubuntu — test and deploy

```bash
bash v178_reservation_redesign_package/deploy_v178.sh
```

The wrapper loads `/etc/hut-reservations/postgres.env`, uses `myprojectenv/bin/python`, checks source, runs the isolated regression suite, collects static files and restarts Gunicorn. No virtual environment activation is needed. Press Ctrl+F5 after success. Check `/r/` and a private reservation link you already have. The bare `/r/` guide intentionally does not display a reservation.

The installer verifies relevant source hashes and prerequisites before writing. Unknown customizations are refused. It creates a private backup and preserves existing file modes; rerunning an already-installed release does not create a second backup.

## Rollback

Use the exact backup path printed by installation:

```bash
bash v178_reservation_redesign_package/rollback_v178.sh summitdesk_backups/reservation_v178_TIMESTAMP
```

Replace `TIMESTAMP` with the printed value. Rollback checks both current source and backup integrity, restores the previous files, collects static assets and restarts Gunicorn. Existing reservation, hut and notification records remain intact.

## Validation

739 tests ran in 13.546 seconds: 733 passed and 6 PostgreSQL-only concurrency tests were skipped under SQLite. Seven new tests cover the three receipt states and original rate calculation; guest/authorized-staff actions and started stays; recovery privacy and staff hut scoping; CSRF and duplicate recovery sends; route/session preservation during language switching; delayed email and payment wording; and the read-only `/r/` guide. Existing navigation assertions were updated to require the new shared public base.

16 installer/rollback checks passed on v177, covering preflight, installation, verification, idempotence, modes, exact restoration, unknown edits, damaged payloads, symlinks, injected write failure, later source edits and changed backups. 22 production-environment checks passed using the actual installed project settings.

Local browser QA used synthetic records: desktop receipt and guide; 390 px Bulgarian receipt; 320 px English confirmed receipt; no page horizontal overflow; 44 px language controls; 48 px contact targets; intact sample email address; and the staff inline confirmation opened without submitting. Functional language switching and recovery POSTs were tested in Django, rather than against the static preview. No private production booking URL or records were used. The live site was not deployed by this session.
