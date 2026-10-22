# SummitDesk V27 — Unified staff hub

## What it does
Read-only landing page for hut managers and cleaners. Managers see room-level reservation occupancy, arrivals, departures, housekeeping task counts and navigation to V11–V26 tools. Cleaners see only their own task counts, tasks and task link. Access uses the existing V25 `staff_tasks.access` hut membership checks.

## Install
1. Back up your current code. Extract ZIP into a staging directory.
2. Copy `floorplans/staff_hub.py` into the existing `floorplans/` package.
3. Copy `floorplans/templates/floorplans/staff_hub.html` into the existing template directory.
4. In `floorplans/urls.py`, add `from . import staff_hub as hub27` and append:

```python
path('<int:hut_id>/hub/', hub27.staff_hub, name='staff_hub'),
```

5. Activate the production virtualenv, set `DJANGO_SETTINGS_MODULE=config.settings_postgres`, load `/etc/hut-reservations/postgres.env`, run `python manage.py check`, then restart gunicorn.
6. Visit `/staff/floorplans/3/hub/` (replace 3 with your hut ID).

No migrations. No changes to reservations or housekeeping data. Does not replace existing homepage or login redirect. Link the hub from your navigation manually if desired.

## Dependencies
Requires V11 calendar, V14 overview, V21 housekeeping, V23 tasks, V24 team, V25 cleaner access, and V26 invitations, with their previously registered URL names. Verify your installed URL names match the template. Existing booking count is **room-level bed places**, not unique occupied physical beds; pending reservations are included. The first eight tasks are ordered by priority text and bed location, not a numeric priority rank.

## Security/testing
GET-only; authenticated and hut-scoped via V25 access. Cleaner dashboard does not query or display reservation metrics or other cleaners' tasks. `python -m py_compile` checks syntax only. Test manager and cleaner access, cross-hut forbidden response, all links, and mobile layout on staging before deploying to production.
