# v171 — A shorter, moving hut story

The homepage history is now four short chapters with one changing photograph: 1936–1937, 1947, 1964 and renovation/remodelling through 2019. The 1977 block and the Sources & historical notes disclosure are removed from the public page. The old large Then & now section is combined with the short history instead of repeating the photographs in a separate large block.

The page scrolls naturally. The active year and photograph follow the reader; each year can also be selected directly. Motion preferences are respected. The archive uses a compact three-column layout on desktop and a swipeable strip on phones. All six photographs and original archive marks are retained.

The /book/ redesign from v170 is included and preserved, together with main-hut-only public booking and the current staff/financial functionality. This cumulative package supports the exact uploaded v167 source, v153.1, v168, v169 and v170. Unknown customizations are refused before source writes.

## Three-step installation

1. PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v171_compact_story.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v171_compact_story.zip
python3 v171_compact_story_package/install_v171.py
```

3. Deploy:

```bash
bash v171_compact_story_package/deploy_v171.sh
```

The deployment script uses myprojectenv/bin/python directly and loads /etc/hut-reservations/postgres.env. It verifies installed source and real project settings, checks Django and migration drift, runs isolated tests, creates a private database backup, applies additive migrations, retains/configures the main hut, collects static files and restarts Gunicorn. If no main hut is set yet, choose Studenets when prompted. Hard refresh with Ctrl+F5 after a successful deployment.

The production checker reads the real project config/settings.py; it does not require a staged settings file inside this package. No new migration is added beyond the established main-hut migration 0027_main_hut_v153_1.

## Rollback

Use the exact private backup path printed by installation:

```bash
bash v171_compact_story_package/rollback_v171.sh summitdesk_backups/story_v171_TIMESTAMP
```

Replace TIMESTAMP with the actual printed path. Rollback guards against later source edits, restores the previous source, collects static files and restarts Gunicorn. Database contents and additive migrations remain. Older source restores that version’s booking rules.

See SHORT_STORY.md, BOOKING_REDESIGN.md and TEST_RESULTS.md for behavior and verification.
