# SummitDesk v145.1 — deterministic CSV export tests

The v145 deployment encountered an existing test-fixture issue: random reservation references can begin with `-`, and the CSV exporter correctly protects those cells by prefixing an apostrophe. Some tests compared the protected CSV value with the raw random reference.

This correction changes only `bookings/test_request_operations_v128.py`. General test fixtures now have deterministic references, and a dedicated regression test always exercises a leading `-`, verifies CSV escaping, and verifies the stored reference/dashboard remain unchanged. Production CSV escaping is preserved.

No migration, booking-data change or database restore is required for this correction. v145 has already installed the runtime changes; resume its deployment script after applying this follow-up.

## Three-step workflow

1. Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v145_1_csv_test_fix.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

2. Ubuntu:

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v145_1_csv_test_fix.zip
python3 v145_1_csv_test_fix_package/install_v145_1.py
```

The installer verifies the original test-file hash, backs it up, and installs the correction. Unexpected customized files are refused. A repeated installation is safe. `--check` checks without modifying files.

3. Resume the existing v145 deployment:

```bash
bash v145_reliability_package/deploy_v145.sh
```

The deployment script repeats its backup/checks safely, applies any still-pending migration, runs the updated isolated tests, then enables the retry timer and restarts Gunicorn. Completed migrations are not applied twice.

## Validation

- Request-operations module: 11 tests passed, including the explicit leading-dash regression.
- Full application suite: 464 tests; 460 passed; 4 PostgreSQL-only concurrency tests skipped.
- Installer dry-run, installation, repeated installation, rollback checks, and exact restoration passed in a disposable local fixture.
- No live server changes were made while creating this package.

To reverse just this test correction, use the backup path printed by the installer:

```bash
python3 v145_1_csv_test_fix_package/rollback_v145_1.py --list
python3 v145_1_csv_test_fix_package/rollback_v145_1.py BACKUP_PATH
```

No service restart is needed to change a test file. Reversing this correction restores the random-reference test failure risk.
