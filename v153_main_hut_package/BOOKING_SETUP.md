# Guest booking flow setup

The code fixes work immediately after deployment. Actual hut contacts, payment methods and reply expectations must be entered by the operator.

## Per-hut information

As a superuser, open **Admin → Bookings → Huts → your hut → Public booking information**.

- Enter the hut's real public phone and email. These appear on its private reservation receipt and in the request email. A blank hut contact may fall back to the operator contact from Public website settings, clearly labelled “Booking support”.
- Check the existing **Location** field. Enter a real map/directions URL for this hut; the operator's office address is not used as hut directions.
- Enter realistic EN/BG reply expectations, if you can commit to them. Without this, guests are told to wait for the manager's emailed decision and contact the hut if arrival is soon. No 24-hour promise is invented.
- Enter the actual EN/BG payment methods, deadlines and deposit terms. Without these, guests are told that the request form collects no payment and the hut manager will confirm how/when to pay. This release adds no online payment processor and changes no payment ledger calculations.

The public form shows the payment explanation before submission. The receipt and guest request email repeat the same configured information. Text is escaped on web pages. An English/Bulgarian fallback is shown if only one version was supplied; web content carries the corresponding language attribute.

## Privacy information

The booking form always explains that details are used to process the request and communicate about the stay. It links to the complete privacy notice when the reviewed notice is published in **Admin → Public website settings**. Enter the accurate operator/processor/retention information before publishing; `PUBLIC_WEBSITE_SETUP.md` contains the checklist inherited from v149.

No new mandatory consent checkbox is added. The short explanation is not a substitute for a complete privacy notice or a legal assessment.

## Error handling and confirmation

- All independent contact, bed and group-size errors are collected in one response. An invalid quantity gets its own error rather than a misleading extra “choose a bed” error.
- The top summary links to each affected input. It receives focus/scroll after reload; the form URL fragment also works without JavaScript. Invalid date refreshes expose the same summary while keeping the previous selection/details.
- Name and Email are visibly required. Phone remains optional, with an arrival-contact explanation; name, email and phone have autofill attributes and the phone keyboard hint.
- No beds selected displays “Choose beds to see the total” in the main and mobile summary. Selected-bed arithmetic is unchanged.
- On mobile, the date panel is followed by rooms; description comes after rooms and decorative fact chips are hidden. The Menu remains beside the logo; language controls have their own row.
- Guest receipts and guest self-service use the public header/footer. Pending requests use “Request received” and “Estimated total”. The receipt names the hut and explains manager approval.
- Guest change/cancellation actions are hidden from started, past and cancelled stays; the existing server-side guest-request guard remains in force. Authorized staff tools are preserved.

## Basic spam protection

There are no third-party CAPTCHA calls or new external services.

- A visually hidden trap field is excluded from keyboard and screen-reader navigation. A filled trap blocks inventory and email writes and shows an error.
- Database-backed counters are shared by all application workers. Defaults: 12 new requests per browser per fixed 10-minute window; 6 per normalized email per hour; 60 per directly available peer IP per 10-minute window.
- Successful retries of the same idempotent submission reuse the existing reservation without consuming another slot. Quota acquisition is inside the locked new-submission transaction.
- A blocked new request returns HTTP 429 and `Retry-After`, retains the entered details, and sends no email or reservation write.
- Counters store HMAC identifiers, count and expiry, never raw email/IP/browser secrets. Up to 100 expired counters are pruned on each new allowed request.
- v151 adds explicit trusted transport/peer support for the optional IP bucket, shared with login protection. Unconfigured or malformed proxy identities still use browser/email budgets; no shared unknown-IP bucket is created. See `LOGIN_PROTECTION.md` for the exact X-Real-IP contract.

Optional production environment tuning (positive integers only): `DJANGO_BOOKING_BROWSER_LIMIT`, `DJANGO_BOOKING_EMAIL_LIMIT`, `DJANGO_BOOKING_IP_LIMIT`. The browser/IP windows are 10 minutes and the email window is one hour. Defaults need no new environment entries.

## After deploying

Hard refresh, then check a missing-bed + invalid-email submission, a valid request, its email and the private receipt on desktop/mobile in EN and БГ. Confirm the hut-specific details entered above are accurate. Browser pixel rendering was not verified in the build environment; the supplied QA report records the checks that were run.
