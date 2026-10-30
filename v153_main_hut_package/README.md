# Карлък v153 — main hut homepage and logo

One cumulative upgrade, including the previous booking, staff workflow, security, media and EN/BG improvements. Supports the supplied source through v143 and packages v145/145.1 through v152. Includes source/database backup and source rollback.

## Three-step upgrade

1. Windows PowerShell:

   ```powershell
   scp "$env:USERPROFILE\Downloads\summitdesk_v153_main_hut.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
   ```

2. Ubuntu:

   ```bash
   cd /home/deploy/hut-reservations
   unzip -o summitdesk_v153_main_hut.zip
   python3 v153_main_hut_package/install_v153.py
   ```

3. Ubuntu:

   ```bash
   bash v153_main_hut_package/deploy_v153.sh
   ```

**If several active huts exist and no main hut is already configured, deployment asks you to choose its number.** The choice is saved in Admin → Public website settings → Main hut. A sole active hut is selected automatically. No hut name or slug is guessed between multiple choices.

The deploy script uses `myprojectenv/bin/python` directly; virtualenv activation is unnecessary. No new dependency or environment variable is required. Hard refresh with Ctrl+F5 afterward.

## Result

- `/` opens the selected hut's own page: photograph, description, rooms, contacts, dates and pending reservation requests. Date checks and submission forms stay at `/`.
- **All huts** remains in the desktop/mobile navigation. Other active huts have information pages and an explicit notice that online booking is unavailable. They have no date picker, bed selector or request form.
- Direct POSTs to other hut pages and forged room selections cannot create reservations. The legacy `/book/` route and public availability endpoint are scoped to the main hut. The selector is checked again under a database lock immediately before a new public request is created.
- Existing reservations, private guest links, staff booking/approval, payments and other assigned hut operations remain available.
- Your uploaded **Карлък** PNG is used unchanged in public branding, footer, staff sidebar, sign-in and Admin. A white CSS badge preserves the original black artwork on dark surfaces. The branded SVG favicon embeds the same original bytes with a white backing.
- Generic Mountain Hut/SummitDesk display names fall back to **Карлък**. A real custom name in Public website settings or HUT_NAME remains respected. Real hut names are retained.

See MAIN_HUT.md, BRANDING.md and QA.md. Earlier setup guides are included.

## Backups and rollback

The installer validates supported hashes and refuses unexpected edits, symlinks and non-file targets before writing. Source backups use `summitdesk_backups/main_hut_v153_<timestamp>/`. Failed installation restores already-written files, including inherited template removals.

Deployment backs up the existing database, applies additive migration **0025**, selects the main hut, runs checks/tests, collects static assets and restarts Gunicorn and the existing notification retry timer. It does not replace nginx, certificate files or operator environment files.

Use the exact backup path printed by the installer:

```bash
cd /home/deploy/hut-reservations
bash v153_main_hut_package/rollback_v153.sh summitdesk_backups/main_hut_v153_<timestamp>
```

Source rollback refuses to overwrite later edits and retains additive schema/data, including the main-hut choice and staff decision history. Restoring older source also restores that version's older public-booking behavior; rollback is not an operational Undo action.
