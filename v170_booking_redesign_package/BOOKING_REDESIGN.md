# Reservation page behavior

The homepage stays at /, the active booking flow at /book/, and the huts list at /huts/. This release changes the booking presentation, with no changes to the booking views, forms, services, original calculator/availability script or financial Admin compared with v169.

## The guest flow

- The header uses the Karlak logo, site name, local fonts and colour palette from the heritage homepage. English/Bulgarian language controls, a skip link, mobile navigation and the footer-only staff link are retained.
- Arrival, departure and group size are in one prominent availability panel before the rooms. On narrow phones, date inputs span a whole row with an inline label, so the full year and native calendar icon fit. Marketing copy and the step-navigation row are reduced on phones.
- The first native GET availability search lands at #rooms with JavaScript enabled. Without JavaScript it remains a normal GET form; server-side validation and room selection remain available.
- Rooms show actual per-bed/night prices, capacity, whole-stay availability and the existing quantity controls. Selected rooms are highlighted. Bed steppers have 44 by 44 pixel controls.
- The desktop sidebar shows the hut photo, selected dates, room breakdown and estimated total. It mirrors the existing calculated summary and does not calculate prices independently or add submission controls. It directs guests to rooms while empty, then to guest details after selection. A sidebar too tall for the viewport scrolls naturally with the page instead of sticking out of reach.
- Phones use the established fixed review link and live total. The sidebar is hidden there. The original review, request button, payment instructions, privacy explanation, autofill attributes, optional phone field and anti-spam fields remain within the protected reservation form.
- Dates can be refreshed without losing entered guest details. The preview follows changed totals, hides when the stay is fully booked, and returns when beds become available. Invalid dates or guest inputs retain the linked, focused error summary.
- The FAQ explains approval, date coverage and changes/cancellation. Real hut contacts and directions are shown when configured. No contact details or current facilities are invented.

## Safeguards retained

The submission is still a pending request, not an instant confirmation. Signed idempotency tokens, CSRF, anti-spam checks, request quotas, the main-hut policy recheck, live capacity checks, guest private access and notification delivery retain their established implementation. The new script reads the existing rendered summary; it neither creates reservations nor sends extra network requests.

The sidebar image uses the hut’s uploaded image if configured, otherwise the supplied Studenets winter photo. Images and fonts are local. This release adds no Google Fonts, trackers, third-party embeds or external JavaScript dependencies.

The receipt and private guest portal retain their existing implementation. This redesign is scoped to the public booking page.

Twenty-four added Bulgarian phrases cover the new headings, sidebar, guidance and navigation. Hut and room names, descriptions and contact details continue to come from the database.
