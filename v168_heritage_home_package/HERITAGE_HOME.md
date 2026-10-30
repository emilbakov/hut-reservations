# Homepage and booking behavior

## Guest pages

| URL | Experience |
| --- | --- |
| `/` | A story-led main-hut homepage. No date, bed, guest-details or reservation form. |
| `/book/` | Dates, room availability, bed quantities, guest details, request review and booking questions. |
| `/huts/` | All active huts, with other huts marked information-only. |
| `/huts/<main>/` | The main-hut story; canonical URL remains `/`. |
| `/huts/<other>/` | Information only, with public booking POSTs refused. |

Older open forms posting to the root or main-hut alias are still validated through the existing protected booking service. New date and request forms always submit to `/book/`. Requests remain pending until approved. CSRF, signed idempotency tokens, quota enforcement, the final main-hut policy check and inventory validation remain enabled.

## Photographs and layout

The supplied current winter photograph is the main hero, with real 640/960/1280-pixel responsive variants and high fetch priority. It is not upscaled or AI-recreated. Archive images are oriented correctly, retain their full composition and source credit strips, and load lazily. The date 1984 comes from the uploaded archive filename; no founding date, construction date, historical statistics or testimonials have been invented.

The original hut appears in its own story section. The 1984 and present-day photographs have an accessible Then / Now switch. All five supplied photographs are accessible through the gallery viewer. Without JavaScript, both period photographs remain visible and gallery links open the full images. The viewer supports previous/next, arrow keys, native Escape and return of keyboard focus. The mobile menu supports Escape and closes after a link is selected.

The desktop and mobile homepage use the existing Karlak logo, English/Bulgarian language controls and a footer-only staff link. No Google Fonts, analytics or embedded third-party maps are added. Local DejaVu fonts include Cyrillic support; see the existing fonts/LICENSE-DejaVu.txt file. Published policies remain linked; unpublished drafts and missing contact details remain hidden. Hut-specific contacts take priority over the public website contact profile.

## Archive source notes

The user supplied the five source images. The two black-and-white web images carry visible credits to Bulgarian Visual Archive / Milena Nikolova and PastVu; those strips are retained, and the photographer/archive attribution is repeated in the gallery captions. The original uploaded files are preserved outside this deployment workflow. Delivered web copies are resized/compressed for the site; none of the historic content is reconstructed.

## Existing functionality

Staff may continue booking and managing all authorized huts. Deposits, payments, refunds, cancellation settlements, private guest links and existing reservations use their established code and permissions. The homepage displays room capacity only; it makes no claim about availability without dates. Real prices and free beds are calculated on the separate booking page.
