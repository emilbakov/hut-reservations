SUMMITDESK v153 — КАРЛЪК ORGANIZATION BRANDING
===========================================

This is a PATCH ZIP. It contains only updated/new project files and is
intended to be extracted into the existing hut-reservations project root.

WHAT CHANGED
- The provided circular Карлък emblem replaces generic mountain symbols on
  the public site, the legacy site header, the staff sidebar, and staff sign-in.
- Public and staff pages use contrast-appropriate black/white transparent logos.
- Staff header branding, login text, browser titles, and key page breadcrumbs
  use Карлък rather than SummitDesk; the underlying software stays unchanged.
- Public footer includes the emblem, and the favicon/touch icon uses the emblem.
- Public website's configured HUT_NAME is retained (booking emails and site
  identity settings are not changed). The software attribution in the footer
  remains 'Powered by SummitDesk'.
- The existing v146 reservation preview is improved: booking reference is shown,
  preview close has accessible labeling, and the reference is selectable.
- The property planner now rejects inactive rooms during client-side validation;
  server-side booking checks remain authoritative.
- Adds branding and property-calendar regression tests; Bulgarian translation
  for the inactive-room warning is included.

INSTALL (Ubuntu / Django)
1. Back up the live project, particularly templates and static directories.
2. Upload summitdesk_v153_karlak_brand.zip to the project directory.
3. Extract from the project root (paths inside this ZIP are relative):

     cd /home/deploy/hut-reservations
     unzip -o summitdesk_v153_karlak_brand.zip

4. With the existing Python virtual environment activated, run:

     python manage.py check
     python manage.py collectstatic --noinput

5. Restart your actual Django/Gunicorn service using its existing service name.
   (No database migrations are required.)
6. Hard refresh browser or clear site cache to see new logos.

TESTING
On the provided snapshot, the Django test suite ran successfully:
575 tests, 4 skipped. Tests used config.settings_test (not production).

     python manage.py test --settings=config.settings_test

NOTE
This ZIP is based on the uploaded summitdesk_v126(3).zip project snapshot,
which already contains v152 code and the v146 reservation preview. If the
production server has newer changes, review the patch before overwriting.
