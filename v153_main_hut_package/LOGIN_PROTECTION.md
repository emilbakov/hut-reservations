# v151 login protection

Protection is active after the normal deployment, with no new service or package dependency. Both `/staff/login/` and `/admin/login/` use the same shared database budgets. GET pages stay available. Existing manager/cleaner/Admin permissions and password verification remain Django's responsibility.

## Defaults

Each fixed 15-minute window permits:

- 5 failed or currently in-flight password checks per client/account pair.
- 20 failed or in-flight checks per resolved IP address, across accounts.
- 20 failed or in-flight checks per browser, across accounts.
- 20 failed or in-flight checks per normalized account name, across clients.

When the client IP cannot be established safely, the pair uses that browser's private session identifier. There is no shared `unknown`, empty-address or loopback IP bucket. The account limit still applies across browsers/IPs, so creating new browser sessions does not remove protection for a target account. Repeated failures can temporarily limit that account; they do not disable every account on the site.

Slots are reserved under database locks **before** password checking and released/finalized afterward. An unsuccessful sign-in consumes its reserved allowance. Successful authentication clears the pair's failures, preserving other requests' in-flight slots and aggregate failure counts. Redirects alone never reset a counter; Django's authentication signals identify success/failure. Invalid-form errors also count. CSRF-rejected submissions never reserve a slot.

A limit returns HTTP 429 with `Retry-After` for the actual remaining window, an EN/BG explanation, and no-store headers. Waiting until the window ends restores access. Resetting the password does not clear these counters. A worker that terminates during authentication can leave its in-flight slot reserved until its window expires. If quota reservation cannot access the database, authentication is not attempted and the response is 503 with a short retry hint.

Counters contain HMAC identifiers, failure/pending counts and expiry; no raw passwords, account names, emails or IP addresses are stored in the counter table. Up to 100 expired rows are pruned on each newly admitted login attempt. Existing Django authentication/session records are unchanged.

## Your Unix-socket nginx deployment

Your existing Gunicorn socket is `/run/gunicorn.sock`. Gunicorn normally leaves `REMOTE_ADDR` empty for this transport. **The safe default is to ignore forwarded identity headers:** browser/account limits work immediately and different guests never share an `unknown` IP allowance.

To additionally enable real-client IP limits, explicitly establish the following contract:

1. In the existing nginx location that proxies to Gunicorn, set **one** directive that overwrites the header:

   ```nginx
   proxy_set_header X-Real-IP $remote_addr;
   ```

   Replace any existing X-Real-IP directive in that location; do not add duplicates or copy a client-supplied value. Preserve the working Unix socket, Host/protocol headers, TLS certificate and media/static locations.

2. Test the nginx configuration and reload it. Only after confirming the header is overwritten, add this to `/etc/hut-reservations/postgres.env`:

   ```bash
   DJANGO_TRUST_UNIX_PROXY=1
   ```

3. Restart Gunicorn to load that explicit setting. A Unix transport is trusted only while `REMOTE_ADDR` is empty; this flag never trusts a direct TCP peer's headers.

The package does not automatically edit nginx or enable forwarding trust. Enabling IP trust is optional; browser/account login protection and browser/email booking protection already work without it.

## TCP reverse proxies

For known TCP proxy peers, set exact proxy CIDRs, for example:

```bash
DJANGO_TRUSTED_PROXY_CIDRS=127.0.0.1/32,::1/128
```

Use the actual proxy addresses. Keep the backend reachable only by those proxies. Each trusted proxy must overwrite `X-Real-IP` with the correct client address. Direct untrusted TCP clients use their socket peer address and cannot choose an identity through forwarding headers. Universal `/0` proxy trust and malformed CIDRs are rejected by the settings/preflight check.

Only a valid single `X-Real-IP` address is accepted from a trusted transport/peer. Missing or malformed trusted headers fall back to browser/account limits; the proxy's own IP is not substituted. `X-Forwarded-For` and the old blanket `DJANGO_BEHIND_PROXY` flag are not used.

The existing v150 booking guard uses this same extraction contract for its optional IP bucket. Its browser/email limits, honeypot, locked idempotent submission and inventory rules remain in place. There is no second booking limiter or file-cache dependency.

## Optional limit tuning

Defaults require no environment changes. Positive integer overrides:

- `DJANGO_LOGIN_PAIR_LIMIT` (5)
- `DJANGO_LOGIN_IP_LIMIT` (20)
- `DJANGO_LOGIN_BROWSER_LIMIT` (20)
- `DJANGO_LOGIN_ACCOUNT_LIMIT` (20)

The account aggregate limit intentionally spans clients; consider actual staff usage when tuning it. These are basic abuse controls, not a guarantee against every distributed bot or denial-of-service attack.

## Local concurrency verification

From the source directory, this command creates and removes its own temporary SQLite database; it does not use the production database:

```bash
python v151_login_protection_package/verify_concurrency_v151.py
```

It sends eight concurrent login checks against a five-slot pair budget and eight concurrent booking-budget requests against a three-slot email budget, using independent connections. This verifies admission and counter updates under parallel access on file-backed SQLite. PostgreSQL-specific concurrency testing still requires a separate PostgreSQL test environment.
