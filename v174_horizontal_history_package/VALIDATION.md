# Validation

- Django system check: no issues.
- The history component renders in Bulgarian and English. Both outputs contain the five chronological periods, short titles and one paragraph per period.
- The final period says that modernisation was completed in 2021. The 1977 section, historical-notes disclosure and their links are absent.
- DOM checks confirm the focusable native scroll region, chronological list, unique IDs and absence of scripts or hidden history chapters.
- The new component stylesheet resolves through Django staticfiles. The HTML preview embeds the original local fonts and styles, contains all five periods and has no external resource references. Stylesheets parse successfully in JSDOM.
- Byte comparison with v173 confirms an exact four-file scope: the history include, its new versioned CSS and the Bulgarian PO/MO catalogues. All other application files are unchanged.
- Preflight, exact four-file installation, installed-source verification, repeated installation without another backup and exact rollback passed from v169, v170 and v173.
- Unknown history-template edits are refused without source writes. Rollback protects later edits to the new stylesheet.
- Deployment and rollback shell syntax, the four payload hashes and final ZIP CRC were checked before delivery.

Validation used Django, its template renderer, source comparisons and JSDOM. A real-browser visual review was not performed in this environment. Open the bundled `PREVIEW.html` to review the layout before installation. Production deployment is performed by the owner using the supplied commands.
