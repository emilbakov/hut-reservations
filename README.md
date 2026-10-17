# Hut reservations

A small Django site where guests book beds in a mountain hut, by room and by night.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_rooms          # three sample rooms, optional
python manage.py createsuperuser     # your login for /admin/
python manage.py runserver
```

- Booking page: http://127.0.0.1:8000/
- Back office: http://127.0.0.1:8000/admin/ (rooms, prices, reservations)
- Tests: `python manage.py test`

Confirmation emails are printed in the terminal until you configure a real mail server.

## How it works

Guests book a number of beds in a room, not a specific bunk. You hand out bunks on arrival.

| File | What is in it |
| --- | --- |
| `bookings/models.py` | `Room`, `Reservation`, `ReservationItem` (beds in one room) |
| `bookings/services.py` | `free_beds()` and `create_reservation()`: all availability rules |
| `bookings/forms.py`, `views.py` | Date search, bed selection, confirmation and cancel pages |
| `bookings/admin.py` | Back office, which also refuses overbooking |
| `config/settings.py` | Hut name, currency, booking limits (bottom of the file) |

Rules worth knowing:

- **Departure day is not a booked night.** One guest can leave and another arrive on the same day.
- **The busiest night decides.** A room with 4 beds and 3 taken on one night of the stay has 1 bed free for the whole stay.
- **No double bookings.** The check and the save happen in one transaction that locks the rooms, so two simultaneous requests are handled one after the other.
- **Pending and confirmed reservations hold beds; cancelled ones do not.**
- **Prices are copied onto the reservation**, so changing a room's price later does not change existing bookings.
- **Guests manage their booking through a private link** (`/r/<code>/`) sent by email. Anyone with the link can cancel, so the code is random and unguessable.

## Before going live

1. Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` and `DJANGO_ALLOWED_HOSTS=yourdomain.com` in the environment.
2. Switch `DATABASES` to PostgreSQL. SQLite works for one small hut, but PostgreSQL locks per room instead of locking the whole database.
3. Configure real email (`EMAIL_HOST` etc.) and set `DEFAULT_FROM_EMAIL` and `BOOKING_NOTIFY_EMAIL`.
4. Run `python manage.py collectstatic` and serve with gunicorn behind nginx, or use a host such as PythonAnywhere, Railway or Render.

## Adding payments later

Set `BOOKING_INITIAL_STATUS = "pending"`, send the guest to the payment provider after `create_reservation()`, and mark the reservation confirmed when the provider's webhook reports success. Run `python manage.py expire_pending` from cron every few minutes to release beds from abandoned checkouts.

## 2026 upgrade

The upgraded interface includes a responsive booking page, accessible form labels,
room cards, an estimated-price display, a reservation summary and a staff dashboard
at `/staff/dashboard/`. Staff can access the dashboard after logging in through
`/admin/`; non-staff visitors are redirected to login.

Booking creation now validates date windows, stay length, quantities, initial status,
and guest details on the server, including direct service calls. The original
per-night inventory checks, transactional locking, price snapshots, and database
schema remain intact. Admin reservation lists include a dashboard shortcut.

### Configuration

Development: `python -m pip install -r requirements.txt`, `python manage.py migrate`,
`python manage.py seed_rooms`, `python manage.py runserver`.

Production: set `DJANGO_DEBUG=0`, a long random `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` (full HTTPS origins),
`DJANGO_FROM_EMAIL`, `BOOKING_NOTIFY_EMAIL`, and `HUT_NAME` as appropriate.
HTTPS redirects, HSTS, and secure cookies are enabled when debug is off.
Only set `DJANGO_SSL_REDIRECT=0` if TLS is intentionally handled elsewhere and
this is necessary for your proxy configuration. Configure your proxy correctly,
use a production database and email backend, and serve collected static assets.

### Quality checks

Run `python manage.py check`, `python manage.py test`, and
`python manage.py check --deploy --settings=config.settings` with production
configuration. The archive was syntax-checked, but the Django suite could not
be executed in the build environment because Django was unavailable.

### Current scope

The staff dashboard shows current occupancy and upcoming arrivals; it is not a
full drag-and-drop calendar. Payments and guest-initiated date changes are not
implemented. Reservation links are bearer secrets: share them privately.


## Phase 3 — guest booking management

- The booking page includes a month-by-month availability calendar. Each day shows the total free beds; the data endpoint (`/availability/calendar/?year=YYYY&month=M`) exposes no guest details.
- Guests can change dates and bed quantities through the private reservation link. Modifications use transactional room locks, validate capacity, and preserve the existing reservation if validation fails. Prices are recalculated using current room rates.
- Cancellation remains available through the private reservation link. Keep booking links confidential; anyone with the link can manage the reservation. For public production deployments, consider adding an email verification step before changes or cancellation.
- Online payments are not included; a payment gateway requires a provider account and additional configuration.
- Run `python manage.py test` to check the added calendar and modification tests.

## Phase 4: staff operations dashboard

Staff users can visit `/staff/dashboard/` to view a month-by-month occupancy calendar,
booked bed-nights, projected accommodation revenue, pending bookings, and upcoming
arrivals. Click a day to expand its reservation list; guest records link to Django
admin for editing. Use **Export CSV** for reservations overlapping the selected month.
The export includes personal guest information and is staff-only. Store exported
files securely. Revenue is a projection calculated from booked nights and the
price saved on each reservation item; it is **not** a payment or accounting ledger.
The occupancy denominator is the currently active room capacity.

Run `python manage.py test` after installing requirements. The Phase 4 test suite
covers staff access, invalid export months, and dashboard rendering.

## Phase 2 — Responsive website redesign

The guest-facing booking page now has a responsive illustrated mountain hero (drawn with CSS, no external images), clearer trust/booking benefits, improved room selection cards, accessible keyboard focus states, a skip-to-content link, and refined desktop/mobile spacing. All Phase 3 booking and Phase 4 dashboard routes remain in place.

No database migration is needed for this design-only update. Run `python manage.py test` after installing requirements.
