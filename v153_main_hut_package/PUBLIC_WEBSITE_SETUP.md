# Set up the public website after deployment

Sign in as a superuser at `/admin/` and open **Bookings → Public website settings → Add**. Only one profile is allowed. Hut managers cannot edit the site's operator details or legal policies.

1. Enter your public brand. A custom existing `HUT_NAME` remains the fallback; the generic `Mountain Hut` fallback now displays as SummitDesk on guest pages. Staff settings and email configuration are unchanged.
2. Enter the real public phone, email, location and map link. Blank details are hidden. Use a full international phone number. The map is a link rather than an embedded third-party widget. For a multi-hut service these are the operator's contact details, not an invented shared hut address.
3. Optionally upload your own licensed hero photograph and descriptive English/Bulgarian alt text. The original must be at least 1920 px wide and smaller than 12 MB. Compress it before uploading; uploaded originals do not receive the bundled photo's responsive variants automatically. Prefer 1920–2560 px WebP around 150–250 KB. The default social-sharing image remains the bundled landscape.
4. Enter reviewed English and Bulgarian policy text. Keep **published** unchecked while drafting. Blank drafts never appear in public navigation and their URLs return 404. Publishing requires an operator name, policy text and (for privacy) an email contact. These checks establish completeness of basic fields, not legal adequacy.

## Privacy notice: information to confirm before publication

The source does not supply your operator identity, contact details, processors, retention schedule or legal decisions. No invented notice has been published.

Have the responsible operator and a qualified adviser confirm the final wording. Describe:

- The legal operator/data controller and its contact details, and DPO if applicable.
- Names, email addresses, phone numbers, booking dates, room/bed selections, messages and any other data actually collected.
- The actual purposes and lawful bases for handling enquiries, reservations, guest messages, accounting and security. Do not add a consent checkbox as a substitute for identifying the appropriate basis.
- Which hut managers, hosting/email providers, accountants or other recipients receive data; any transfers outside the EEA and relevant safeguards.
- Actual retention periods or clear criteria, including bookings, messages, logs and backups.
- Applicable access, correction, erasure, restriction, portability and objection rights, and withdrawal where consent is used.
- How guests contact the operator and complain to the competent supervisory authority.
- Which data are required to process a booking and what happens if they are omitted; any automated decisions, if applicable.
- The site's actual session/security/language cookies and third-party resources. The existing legacy `/book/` shell loads Google Fonts; account for the deployed configuration rather than claiming there are no third-party connections.

Published privacy links appear in the footer and next to personal details on both active public booking forms. Policy content is rendered as escaped plain text with paragraphs; HTML/scripts are not allowed. If only one translation is supplied, that language is labelled and a fallback notice is shown.

## Cancellation policy: operator decisions required

Describe deadlines, fees, refunds, no-shows, weather/access arrangements, contacts and any hut-specific differences. Do not promise free cancellation or a refund unless those are the actual agreed terms.

The existing software flow is preserved: the guest uses the private email link to request a change/cancellation; the manager reviews the request and applies approved booking updates. A request alone does not change availability or the reservation. The FAQ explains this flow without inventing financial terms.

## Language and assets

The EN/БГ switch and existing Bulgarian booking/planner support are preserved. New footer, FAQ, policy labels, notices and landscape alt text are translated. Your own hut descriptions, contact addresses and policies require your own translations.

Actual hut photos remain unchanged on disk. Cards use a consistent 3:2 display crop and a restrained shared CSS color treatment. This cannot recover detail missing from the original hut uploads.

Photo source and licence: see `ASSET_CREDITS.md`. The bundled image is a regional landscape, not a photograph of any listed accommodation.

## After deployment

- Hard refresh and check the homepage and one booking flow at desktop and mobile widths, in EN and БГ.
- Add real contact information and publish reviewed policy text before treating the footer/legal setup as complete.
- Open a `/media/huts/...` image URL. Your existing nginx `/media/` alias must still match `DJANGO_MEDIA_ROOT` (v148 default `/var/www/hut-media/`). New optional hero uploads use `/media/site/` under the same root.
- The installer does not edit nginx, certificates, renewal timers or operator environment settings.
- Social networks may cache older link previews; request a refresh through the relevant platform after deployment.
