# v173 — Only the history block shown in the screenshot

This small patch keeps the existing homepage and history layout. It changes exactly three source files: the history template and its Bulgarian PO/MO translation catalogues.

- The original 1936–1937, 1946–1947, 1950s–1960 and 1964 entries remain.
- The 1977 entry, its capacity/facilities box and booking link are removed.
- The short 1977 guidebook note under 1964 is removed.
- A 2021 entry states that the hut's modernisation was **completed** in 2021, as supplied by the owner. It does not say that work began in 2021.
- The “Sources & historical notes” / “Източници и исторически бележки” disclosure and its links are removed.

The new Bulgarian row reads:

**2021 — Завършена модернизация**

През 2021 г. завършва модернизацията на хижа „Студенец“. Нова глава за познатото място в сърцето на Пампорово.

No homepage wrapper, CSS, photograph, navigation, booking page, Python application source or database record is changed. The deployment does not run migrations or configure the main hut. No other release needs to be installed first.

## 1. PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v173_history_edit.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Ubuntu: install

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v173_history_edit.zip
python3 v173_history_edit_package/install_v173.py
```

## 3. Ubuntu: deploy

```bash
bash v173_history_edit_package/deploy_v173.sh
```

After success, hard refresh with Ctrl+F5. The wrapper loads the existing production environment and uses `myprojectenv/bin/python` directly.

Supported source: the original v169/v170 history shown in the screenshot, including that source restored by previous rollback scripts. Unknown edits are refused before source writes. If the later v171/v172 redesign is still active, first use that release's rollback to return to the screenshot layout.

## Rollback

Use the exact backup path printed by installation:

```bash
bash v173_history_edit_package/rollback_v173.sh summitdesk_backups/history_edit_v173_TIMESTAMP
```

Replace `TIMESTAMP` with the actual printed timestamp. Source and backup integrity are checked before restoration. Booking data is retained.
