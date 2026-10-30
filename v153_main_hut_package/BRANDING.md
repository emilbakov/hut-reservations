# Карлък branding

The supplied 1254×1254 transparent PNG is copied byte-for-byte to `static/bookings/brand/karlak-logo-v153.png`. Its artwork has not been redrawn, recolored or cropped. A white CSS badge makes the black logo legible on the forest-colored staff surfaces. Logo images have explicit dimensions and adjacent text provides the brand name; repeated decorative image text is hidden from screen readers.

The SVG favicon embeds exactly the same PNG bytes and adds a white SVG backing. The original PNG is also the fallback and touch-icon asset. These are versioned paths so existing cached icons do not retain the old generic mark. Browser/home-screen icon rendering has not been visually verified.

Updated surfaces include public header/footer, legacy guest receipt shell, staff sidebar, desktop/mobile staff sign-in, login-limit page, Admin header, and standalone hut-operation pages. Older split Summit/Desk wordmarks and a dynamically generated operations sidebar have also been replaced. The dynamic sidebar reads the brand name through inert JSON, not HTML interpolation.

Display-name precedence is a real custom name in Public website settings, then a real HUT_NAME setting, then Карлък. Blank/Mountain Hut/SummitDesk placeholders use Карлък. Actual hut names, public operator/policy fields, historical notifications and stored guest data are not renamed. Internal code names and package filenames stay compatible.

The Admin override is in the project template directory; the normal Django Admin forms, permissions and color-theme control are retained. During a login-protection database outage, the failure page uses the configured/default brand without querying the unavailable database again.
