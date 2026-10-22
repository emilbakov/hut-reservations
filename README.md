# Safe PostgreSQL trial migration (no live switch)

Your production app continues using SQLite. The source is the verified SQLite backup,
not the live SQLite file. PostgreSQL destination is `hut_reservations`.

**Prerequisites:** The PostgreSQL database `hut_reservations` must exist, belong to
`hut_app`, and be EMPTY. Do not run this on a populated database. Do not use a
production PostgreSQL database as the destination.

1. Upload `prepare_trial.py` and `verify_trial.py` into `/home/deploy/hut-reservations`.
2. From your activated venv in that directory, run:

```bash
python prepare_trial.py
```

3. Copy the printed settings module names. Below `PROJECT` is a placeholder for
   the module prefix printed by the script (e.g. `myproject`).

4. Supply PostgreSQL password for this shell session, without putting it into history:

```bash
read -rsp 'PostgreSQL hut_app password: ' HUT_PG_PASSWORD; echo
export HUT_PG_PASSWORD
```

5. Verify the PostgreSQL destination is empty (if it contains tables, STOP):

```bash
PGPASSWORD="$HUT_PG_PASSWORD" psql -h 127.0.0.1 -U hut_app -d hut_reservations \
  -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
```

This must output `0`. If not, stop and investigate; do not drop any tables.

6. Export the snapshot, excluding content types and permissions that `migrate`
   recreates. **Replace `PROJECT` with the module prefix printed by step 2**:

```bash
python manage.py dumpdata --settings=PROJECT.settings_sqlite_trial \
  --natural-foreign --natural-primary \
  --exclude=contenttypes --exclude=auth.permission \
  --indent=2 --output=/home/deploy/reservation-backups/sqlite-trial-data.json
```

7. Initialize the PostgreSQL schema and import:

```bash
python manage.py migrate --settings=PROJECT.settings_postgres_trial --noinput
python manage.py loaddata --settings=PROJECT.settings_postgres_trial \
  /home/deploy/reservation-backups/sqlite-trial-data.json
```

8. Compare source and destination model counts:

```bash
python manage.py shell --settings=PROJECT.settings_sqlite_trial < verify_trial.py \
  > /home/deploy/reservation-backups/sqlite-trial-counts.txt
python manage.py shell --settings=PROJECT.settings_postgres_trial < verify_trial.py \
  > /home/deploy/reservation-backups/postgres-trial-counts.txt
# Review model counts, excluding content types and auth permissions
cat /home/deploy/reservation-backups/{sqlite-trial-counts,postgres-trial-counts}.txt
```

The `TOTAL ROWS` and each model's count must match. Inspect any discrepancies.
Check data beyond counts (FKs, dates, totals, and guest access) before cutover.

9. Run PostgreSQL tests using isolated trial settings. Django's test runner
   normally creates a *separate* PostgreSQL test database, requiring CREATEDB:

```bash
python manage.py test bookings.test_postgres_concurrency \
  --settings=PROJECT.settings_postgres_trial -v 2
```

10. **Do not change production `settings.py` or restart Gunicorn.** The live
application is still on SQLite. Before any actual cutover, stop booking writes,
take a new final snapshot, and repeat the transfer to a newly empty destination.

Security: Keep JSON fixtures and backups private; they contain guest data and
possibly password hashes and private guest links. Use `chmod 600` on exports.
Avoid exposing the database port publicly.
