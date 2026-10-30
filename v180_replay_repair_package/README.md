# v180 booking replay test repair

This small recovery package has a distinct filename: `summitdesk_v180_replay_repair.zip`. It repairs the original or updated v180 deployment bundle already present on the server, then resumes the normal deployment.

The reported line `browser=Client();token=browser.get(url).context['submission_token']` belongs to the old test. That test reads the hut heritage homepage, which has no booking token. The corrected test explicitly selects its synthetic main hut and uses `/book/`. A route/repeated-submission regression now runs on SQLite too; the simultaneous replay check continues to run on PostgreSQL.

## 1. Upload from Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v180_replay_repair.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Stage the repair on Ubuntu

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v180_replay_repair.zip
python3 v180_replay_repair_package/install_replay_repair.py
```

The installer checks known original/corrected source hashes. It backs up and updates only the staged replay-test payload, its deployment metadata, and the deployment wrapper's verification gate. It does not replace live application source at this step, query the database, or change settings. Customized/unrecognized files are refused before writes. Rerunning is safe.

## 3. Resume deployment

```bash
bash v180_replay_repair_package/deploy_replay_repair.sh
```

The normal v180 installer applies the corrected test, preserving its ordinary application-source backup. Before running any tests, deployment now prints:

```text
v180 replay repair verified: corrected /book/ fixture installed.
```

If that exact replacement is absent, deployment stops before the suite runs. Otherwise it continues with the normal v180 migration/checks, SQLite suite, isolated PostgreSQL suite, static collection, systemd jobs and Gunicorn start. No database rollback is needed. PostgreSQL tests use the original isolated temporary-database workflow; no check is disabled.

If deployment fails at a later check, its existing behavior leaves Gunicorn stopped and prints the error. Keep the complete new error output for diagnosis. This package has not been executed on your server from this session.

## Staging rollback

The installer prints a private staging-backup path. To restore only those staged deployment files:

```bash
python3 v180_replay_repair_package/install_replay_repair.py --restore summitdesk_backups/replay_repair_v180_TIMESTAMP
```

Use the exact printed path. This restores the prior deployment bundle, not live application source or database records. Restoring the original staged test restores the reported test failure too. Application rollback remains the ordinary v180 source-backup workflow; use the most recent source-backup path printed during deployment. Backup contents and later edits are checked before restoration.

## Validation

28 checks covered staging and normal installation from original v180 and already-corrected bundles, installed-file verification before tests, idempotence, private backups, staging restore, preservation of unrelated source files, customized-file/symlink rejection and recovery from an injected write failure. The 36-test reliability suite passed locally with its one PostgreSQL-only check skipped. The full corrected v180 suite was previously verified locally with 785 tests run and nine PostgreSQL checks skipped. Actual PostgreSQL concurrency verification runs on the server during deployment.
