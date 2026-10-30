# Staff workflow v152

## Dashboard counts

- **Needs your decision:** authorized pending reservations, including manual pending bookings. The oldest three are shown with inline actions; All pending requests opens the Reservations list filtered to every pending booking, including manual ones. The separate public request queue remains limited to guest requests.
- **Arrivals / Departures today:** confirmed bookings scheduled for that date, not people or bed counts. Pending requests stay in the decision queue.
- **Checked in now:** confirmed bookings with an actual check-in recorded and no actual check-out. It uses the same definition as Arrivals & departures.
- **Beds held tonight:** expected occupied beds from pending and confirmed reservations whose arrival <= today < departure. This can differ from actual checked-in bookings and is labeled separately.

The public approval queue remains limited to public guest requests. A pending historical mixed-hut reservation needs administrator review; a manager cannot approve a partial booking.

## Approve and decline

The capacity panel shows each room's requested beds, the minimum free beds across all stay nights before this request, and the remaining beds after approval. It excludes the request's own pending hold, counts all other pending/confirmed reservations and distinct maintenance closures, and checks room activity.

Approve opens an inline review with a final submit button. The POST checks authorization and locks the reservation and rooms in the same order as the existing services, then recomputes capacity. An old page cannot approve a new conflict. Conflicts remain pending with an error. Guest confirmation is queued for public requests with the existing notification service; staff-created pending bookings retain their prior email behavior.

Decline opens an optional plain-text reason (maximum 1,000 characters), then a final submit button. This releases the hold. The decision record stores reservation, actor, previous/new statuses, reason and time. The public guest's decline email includes the reason; the declined request card shows it as escaped text. No guest-supplied text is interpreted as HTML.

## Undo

A recent decision receipt appears after approval/decline on the dashboard, queue or reservation list. Undo applies only when the previous status was pending, within five minutes and by the same authorized user. It checks:

- The decision is the latest one, has not already been undone and its resulting status still matches.
- Booking identity, notes, dates, item quantities/prices and the reservation audit revision match the saved fingerprint. Edits followed by restoration still invalidate the receipt through the audit revision.
- No actual check-in exists, and restoring the pending hold fits the current active room capacity on every night.

Undo returns to pending. A decline cannot be undone if the released beds have been booked by someone else. No overbooking override is provided. Duplicate Undo does not create another correction. Unsent prior decision emails are marked skipped. Public requests with an email get a new pending-status correction; an email already delivered cannot be recalled. Another approval after Undo is a distinct notification event, so deduplication does not suppress it.

The source rollback script does not undo reservation decisions or delete audit data. Operator changes that bypass normal model save/audit behavior are outside the Undo edit-detection contract.

## Calendar views

- **Bookings:** seven-day booking calendar. Mobile opens the vertical week list, with one expandable section per day, room free counts, closure counts and visible authorized bookings. Timeline shows bars across occupied nights. Selecting a booking opens the existing details/edit drawer; direct links work when dialogs are unsupported.
- **Free beds:** monthly availability overview with per-night counts and links to the validated booking form.
- **Room ledger:** monthly room/physical-bed detail view, including maintenance and bed-management links.

These are distinct views of the same reservations, not separate calendars that need manual synchronization. Checkout day does not use a bed. Historical mixed-hut items consume capacity without exposing their guests to a partial manager. Changes to the date/hut apply immediately when JavaScript is available; the submit button remains usable without JavaScript. The view toggle is only shown when JavaScript is active. Existing drag/move validation remains in place on the timeline.

## Fonts and accessibility

Staff navigation and the shared guest receipt shell use local DejaVu Sans files under `static/bookings/fonts/`; the full Bitstream Vera/DejaVu license is included there. CSS aliases preserve the old family hooks but use the bundled typeface. No Google font stylesheet/preconnect remains in the project templates.

Targeted staff small text has a 13px minimum; contact, sign-out, public-site and main action targets have a 44px minimum. A staff skip link leads to focusable main content. Native details/forms provide keyboard access and work without scripting. Visual checks on a real mobile browser are still needed before claiming precise fold heights or universal touch-target compliance.

This release addresses the reported overview, arrivals, approval and calendar issues and shared navigation/readability. It does not claim a visual review of Finances, Expenses, Deposits, editors, conversations or Reports.

## Optional concurrency verification

From the project directory:

```bash
python3 v152_staff_workflow_package/verify_concurrency_v152.py
```

This always creates a temporary local SQLite database and never uses the production database. It checks login and booking quota contention and competing Undo/new bookings for one released bed. It does not establish PostgreSQL concurrency behavior. PostgreSQL-only tests require a separate suitable test environment.
