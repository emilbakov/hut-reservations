# v180 socket startup order repair

The journal identifies the deployment failure:

```text
gunicorn.socket: Socket service gunicorn.service already active, refusing.
```

The deployment wrapper started Gunicorn before starting its socket. This repair changes the order in both deployment and source rollback: start the socket first when a socket unit exists, then start Gunicorn. The no-socket configuration still starts Gunicorn normally.

The newest supplied journal already shows the socket listening and both workers booting. This repair does not restart, stop or otherwise operate running services. It fixes the scripts used by future deployments and rollbacks. It does not change Django source, reservations, database schema, email settings, systemd unit files or the existing replay-test verification gate. The HEAD/404 response-body warnings in the journal are separate and are not changed by this repair.

## 1. Upload from Windows PowerShell

```powershell
scp "$env:USERPROFILE\Downloads\summitdesk_v180_startup_repair.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/
```

## 2. Install on Ubuntu — no restart

```bash
cd /home/deploy/hut-reservations
unzip -o summitdesk_v180_startup_repair.zip
python3 v180_startup_repair_package/install_startup_repair.py
```

The installer accepts known original v180 and replay-repaired wrappers, including already-corrected startup variants. It preserves each wrapper's other bytes, creates a private backup, preserves modes, checks shell syntax and refuses customized/unknown files before changing anything. Repeating installation is safe. It takes the normal deployment lock so it cannot write while a deployment or rollback holds that lock.

## 3. Verify — no restart

```bash
python3 v180_startup_repair_package/install_startup_repair.py --verify-staged
```

Expected output:

```text
Startup order verified: socket before Gunicorn. No services restarted.
```

The next normal deployment uses the corrected existing script:

```bash
bash v180_deposit_flow_package/deploy_v180.sh
```

There is no need to deploy again merely to install this repair. Extracting an older full release/repair over these scripts can replace the fix, so retain this repair with the release for recovery.

## Undo this script repair

Use the exact staging-backup path printed by installation:

```bash
python3 v180_startup_repair_package/install_startup_repair.py --restore summitdesk_backups/startup_repair_v180_TIMESTAMP
```

This restores the two previous shell scripts and their modes without operating services or touching the database. Later edits or altered backup contents are refused. Restoring the old scripts also restores their incorrect startup order.

## Validation

22 checks passed for original and replay-repaired v180 wrappers: read-only preflight, exact preservation of all bytes except the startup order, preservation of the replay-test gate, modes, idempotence, backup/restore, customized-file rejection and shell syntax. Simulated service control reproduced the production refusal for the original order, and verified socket-first startup plus the no-socket fallback. These checks did not operate your live server. No Django behavior was changed, so the application suite was not rerun for this script-only fix.
