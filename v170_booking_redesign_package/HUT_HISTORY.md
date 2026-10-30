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

The supplied current winter photograph is the main hero, with real 640/960/1280-pixel responsive variants and high fetch priority. It is not upscaled or AI-recreated. Archive images are oriented correctly, retain their full composition and source credit strips, and load lazily. The date 1984 comes from the uploaded archive filename. The added postcard is undated and is not assigned a historical year. Published historical dates and statistics are explained below.

The original hut appears in its own story section. The 1984 and present-day photographs have an accessible Then / Now switch. All six supplied photographs are accessible through the gallery viewer. Without JavaScript, both period photographs remain visible and gallery links open the full images. The viewer supports previous/next, arrow keys, native Escape and return of keyboard focus. The mobile menu supports Escape and closes after a link is selected.

The desktop and mobile homepage use the existing Karlak logo, English/Bulgarian language controls and a footer-only staff link. No Google Fonts, analytics or embedded third-party maps are added. Local DejaVu fonts include Cyrillic support; see the existing fonts/LICENSE-DejaVu.txt file. Published policies remain linked; unpublished drafts and missing contact details remain hidden. Hut-specific contacts take priority over the public website contact profile.

## Archive source notes

The user supplied the six source images. The two black-and-white web images carry visible credits to Bulgarian Visual Archive / Milena Nikolova and PastVu; those strips are retained, and the photographer/archive attribution is repeated in the gallery captions. The original uploaded files are preserved outside this deployment workflow. The first five delivered web copies are resized/compressed for the site; none of the historic content is reconstructed. The newly added retro-043.jpg is an exact byte-for-byte copy of the uploaded image, including its archives.bg watermark, border and handwritten caption.

## Existing functionality

Staff may continue booking and managing all authorized huts. Deposits, payments, refunds, cancellation settlements, private guest links and existing reservations use their established code and permissions. The homepage displays room capacity only; it makes no claim about availability without dates. Real prices and free beds are calculated on the separate booking page.

## Historical content in v169

The story distinguishes the original hut from the larger building opened on 28 October 1964. It does not claim that the hut preceded the founding of Pamporovo itself. The connection with the development of skiing and infrastructure is presented as part of the hut’s role in the growing resort.

The timeline includes:

- 1936–1937: tourists from Chepelare establish a refuge in the former border post. Eho gives 1936 for the conversion and identifies the old Bulgarian–Turkish border as the one that existed until 1912.
- 1946–1947: fire followed by rebuilding the next year.
- The 1950s and 1960: the Stenata piste and the lift routes envisaged in the regional scheme. Planned infrastructure is explicitly described as planned, not already built in 1960.
- 28 October 1964: the ceremonial opening of the larger hut. The two construction periods, 1962–1964 and 1960–1964, are retained with attribution.
- 1977: a historical snapshot of 170 accommodation places and 90 restaurant seats, with the period facilities. These values are content only and never change room inventory or today’s availability. The panel directs guests to the separate booking page for present-day information.

The four sources are linked in the expandable “Sources & historical notes” area. This uses native HTML details, works without JavaScript and introduces no requests to these sites until a guest follows a link.

1. Eho, Bulgarian Tourist Union, issue 2 (2031), February 2025, p. 12: https://www.btsbg.org/file/3636/download?token=jc6RJGIm#page=12
2. The hut’s own historical account: https://www.studenets.eu/studenets.html
3. Pamporovo planning document, National Centre for Regional Development, 2020, §2.4.1, printed p. 84, hosted by MOEW: https://www.moew.government.bg/static/media/ups/articles/attachments/Zapiska_Pamporvo_IOUP_PPfb3839c2ea30b67a77923dfc3b3ccb17.pdf
4. Huts in Bulgaria, H. Peychev, P. Bozhkov and D. Dushkov, third edition, 1977, separate old/new Studenets entries: https://chitanka.info/text/40755-hizhite-v-bylgarija/12

The Eho PDF, hut history and guidebook were directly opened during verification. The MOEW PDF exceeds the browsing fetch size limit; its relevant indexed text was checked, including the first piste and the lift proposals. No new current capacity, operating contact or facility claims are imported from these historical sources.

Forty-one added Bulgarian translations cover the timeline, source descriptions, new hero wording and postcard caption/alt text. Text and photographs remain on the homepage; booking stays on /book/.
