# Main hut and public reservations

## Selecting the main hut

During deployment, after migration and database backup, `configure_main_hut_v153.py` keeps an existing active choice, automatically selects a sole active hut, or prompts with the real active hut names/slugs and asks for a number. A non-interactive run with multiple huts and no choice stops without guessing. No active huts also stops with an instruction to add one in Admin. No source edit or extra dependency is needed.

Change the selection later in **Admin → Public website settings → Main hut**. This takes effect on new requests without a restart. Only active huts can be selected. The selected main hut is protected against deletion until the choice is changed. Retiring an explicitly selected hut disables public booking rather than switching silently to another hut.

Before explicit selection, a sole active hut can serve as the safe default. With several active huts and no selection, the public site remains an information-only directory and accepts no public reservation requests. The deploy helper saves an explicit choice before restarting the new application.

For scripted configuration, the helper supports `--hut EXACT-SLUG` and read-only `--check`; run it with the project's existing interpreter and production environment already loaded, as the deploy script does. Never substitute a guessed hut slug.

## Guest routes

| Route | Behavior |
| --- | --- |
| `/` | The selected hut's page and reservation flow. |
| `/huts/` | Name/location search and an information-only list of all active huts, with the main hut marked as bookable. |
| `/huts/<main-slug>/` | Compatible alias of the main hut page; canonical URL and form targets are `/`. |
| `/huts/<other-slug>/` | Description, photograph, rooms and contacts; no online reservation controls. POST returns 403. |
| `/book/` | Legacy booking form, restricted to the main hut and its active rooms. |
| `/availability/calendar/` | Public availability for the main hut only. Other hut slugs return 404. |

Directory date/bed search has been removed. Guests choose dates on the main hut's page. Other huts remain visible even when legacy date parameters appear in a directory URL. No public availability count or reservation promise is made for those other huts.

The main page uses its existing hut photograph, then an owner-configured homepage photograph if present, then the existing licensed responsive mountain landscape. It includes the hut description, room list, contact/directions, booking dates and FAQ. Unset contact details are not invented.

## Enforcement

The booking view resolves the current main hut before rendering or handling a public form. A POST to a different hut is rejected before creating a submission, reserving quota or queuing email. The legacy form lists only main-hut rooms. Nonzero foreign room fields are rejected rather than silently accepted.

Immediately before creating a new public booking, the submission transaction locks the public profile and selected hut and rechecks the choice, then uses the existing quota/idempotency/inventory service. A selector change between page load and submit cannot authorize the old hut. A cached page or crafted URL cannot bypass the policy.

A new guest request still starts as pending, holds beds, requires manager approval and uses the existing email retry/private-link flow. This release changes which hut accepts new public requests, not those confirmation rules.

Staff may continue creating and managing reservations for every authorized hut through staff tools. Existing guest receipts, private links, change requests and historical bookings remain accessible under their existing permissions. Inactive huts remain hidden from the public directory.
