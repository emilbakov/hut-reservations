# Booking journey verification — 29 October 2026

## Result

- Original source: 709 tests executed, 703 passed and 6 PostgreSQL-only tests skipped.
- Corrected source with 11 new integration tests: **720 tests executed in 13.522 seconds; 714 passed and 6 PostgreSQL-only tests skipped**.
- Existing frontend booking checks: **64 EN/BG checks passed** using JSDOM, including live totals, date refreshes, sold-out recovery, retained guest details, linked error summaries and navigation.
- Production-environment installer checks: **22 passed**.

All local booking/email tests used synthetic guests, a separate test database and Django's in-memory email backend. No production record was changed and no real email was sent.

## Reproduced defect and correction

The guest change-request review handler recorded the manager's decision and then called email directly in a best-effort callback. When SMTP failed, the callback discarded the exception and created no delivery record. The review appeared complete, but the guest email could not be retried.

The new integration case `test_failed_guest_request_review_email_is_persisted_and_retryable` reproduced this before the fix: expected one failed queued guest-review email, found zero.

The corrected handler creates a `change_review_guest` queue record in the same transaction as the review, keyed by the change-request ID. The existing queue delivers after commit, saves delivery failures and retries due messages. After the fix, the failing case passes: the decision remains recorded, a failed notification exists, retry captures exactly one message, and repeating the review adds no further message.

## Verified journey

| Case | Verified outcome |
| --- | --- |
| HTTPS booking form with CSRF and a signed submission token | A guest creates one pending request for the selected main hut. |
| Price calculation | 2 beds × €18.00 × 2 nights = €72.00; forged client price fields do not alter it. |
| Initial guest/manager messages | Both captured messages are generated; the manager message contains no guest-private access link. |
| Receipt and private email link | The guest can view the receipt and open the token-based portal from another browser session. |
| Manager approval | The reservation becomes confirmed; held inventory remains held. |
| Guest cancellation request and manager review | The review alone leaves the confirmed booking and beds intact, matching the documented manual-processing workflow. |
| Applying cancellation and rebooking | The original record remains cancelled, all three beds become free, and a replacement request succeeds at the expected price. |
| Direct decline with reason | The guest message includes the reason and capacity is released. |
| Double booking submission / repeated approval or cancellation | No duplicate booking, manager decision or guest email is created by repeated actions. |
| Two guests load the same availability before submitting | The second request is rejected when two beds no longer fit; no overbooking or extra notification is created. |
| SMTP outage during initial submission | The pending booking and held beds survive; failed guest/manager messages remain queued and retry successfully once. |
| Approval while initial messages are still failed | Obsolete “awaiting approval” messages are skipped; retry does not send them after confirmation. |
| SMTP outage after reviewing a change/cancellation request | The review is committed and the failed guest message is retained for retry. |
| Two distinct reviewed guest requests | Each creates its own notification; repeated reviews do not duplicate either message. |
| Database failure while queuing a review notification | Both review and notification roll back together; no premature email is sent. |
| Bulgarian guest | The receipt and request email are Bulgarian; the receipt displays the correctly localised €72.00 total. |
| Missing CSRF / another hut's manager | The unauthorized requests cannot create or approve the booking or change its inventory. |

## Package checks

- Exact two-file installation, installed-source verification, repeat-install idempotence, file-mode preservation and exact rollback passed from v169, v170, v173 and v174.
- Unknown target/prerequisite edits and corrupted payloads are rejected before source writes.
- Rollback protects later code changes and detects backup corruption.
- An injected failure on the second source write restores the previous source bytes.
- Symlink source targets are refused.
- Source comparison confirms that all UI templates, static assets, pricing and inventory implementation files remain byte-identical to v174.
- The SMTP diagnostic passed its configured case and seven misconfiguration cases, including authentication without TLS/SSL. Its real isolated queue query, no-connect path and mocked connection success/failure paths were exercised. These paths neither send messages nor expose configured account values or raw SMTP exception contents.
- Shell syntax, final payload hashes and ZIP CRC are checked before delivery.

## Practical limits

The new journeys exercise real Django HTTP views, CSRF checks, session-bound forms, database commits and notification callbacks. The frontend checks use a DOM environment; these are not tests against the live production website.

The local database is SQLite. The six PostgreSQL-only tests remain skipped, so production PostgreSQL concurrency behaviour is not claimed as tested here. The production SMTP connection and actual guest/manager inbox delivery remain unverified until checked on the server. The supplied `--connect` diagnostic verifies only the connection/authentication step and does not send an email.

SMTP itself retains the existing at-least-once delivery behaviour: a process failure after remote acceptance can cause a retry. The patch's deduplication protects repeated application actions; it does not claim exactly-once delivery across SMTP failures.
