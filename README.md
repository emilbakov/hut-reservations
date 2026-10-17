# Reservation Conflict Protection — regression tests

Adds 11 read-only regression tests to `bookings/test_reservation_conflicts.py`.
No production code or schema changes. Existing code was reviewed from the uploaded source archive.

Install from the Django project root (back up first):

```bash
unzip -o reservation_conflict_protection.zip
python manage.py test bookings.test_reservation_conflicts
python manage.py test bookings
```

Expected: 190 tests (179 previous + 11 new).

**Concurrency note:** These tests do **not** prove concurrent transaction safety. That requires
PostgreSQL-backed `TransactionTestCase` tests running with separate database connections,
and deployment-specific validation. SQLite test databases cannot verify PostgreSQL row-lock behavior.

**Other limitations:** Tests use standard test models and verify service behavior and view
permission paths, but have not been executed against the server's Django environment.
