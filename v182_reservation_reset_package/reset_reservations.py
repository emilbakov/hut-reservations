#!/usr/bin/env python3
"""One-off PostgreSQL reservation reset. No application source is installed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

# Child tables precede their parents. The approved-terms cycle is detached first.
DELETE_LABELS = (
    'bookings.BedAssignment', 'bookings.PublicBookingSubmission',
    'bookings.ReservationNotification', 'bookings.GuestStay',
    'bookings.DepositReminderLog', 'bookings.ReservationLifecycleEvent',
    'bookings.GuestMessageLog', 'bookings.GuestAccessLink',
    'bookings.GuestChangeRequest', 'bookings.GuestConversationMessage',
    'bookings.PreArrivalReminder', 'bookings.ReservationDecision',
    'bookings.PaymentTransaction', 'bookings.CancellationSettlement',
    'bookings.ReservationDepositRequest', 'bookings.ReservationItem',
    'floorplans.ReservationHistoryEvent', 'bookings.ManagerRequestDigestLog',
    'bookings.Reservation',
)
PARTIAL_LABEL = 'floorplans.BedCleaningEvent'


def configure(root):
    root = Path(root).resolve(strict=True)
    if not (root / 'manage.py').is_file():
        raise RuntimeError('Run from the hut-reservations project directory.')
    sys.path.insert(0, str(root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_postgres')
    import django
    django.setup()
    return root


def models_and_guard(connection):
    from django.apps import apps
    models = [apps.get_model(label) for label in DELETE_LABELS]
    partial = apps.get_model(PARTIAL_LABEL)
    expected = {m._meta.db_table for m in models} | {partial._meta.db_table}
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        if not expected <= tables:
            raise RuntimeError('Required v180/v181 reservation tables are missing; no changes made.')
        # Unknown foreign keys could cascade outside the scope or leave dangling rows.
        for table in sorted(tables):
            for constraint in connection.introspection.get_constraints(cursor, table).values():
                fk = constraint.get('foreign_key')
                if fk and fk[0] in expected and table not in expected:
                    raise RuntimeError(f'Unexpected related table {table}. Reset refused; inspect its reservation relationship.')
    reservation = apps.get_model('bookings.Reservation')
    reservation._meta.get_field('deposit_request')
    return models, partial


def admin_scope(connection):
    from django.apps import apps
    from django.db.models import Q
    from django.contrib.admin.models import LogEntry
    labels = DELETE_LABELS + ('bookings.DepositEntry',)
    query = Q(pk__in=[])
    for label in labels:
        model = apps.get_model(label)
        query |= Q(content_type__app_label=model._meta.app_label,
                   content_type__model=model._meta.model_name)
    return LogEntry.objects.using(connection.alias).filter(query)


def counts(connection):
    models, partial = models_and_guard(connection)
    rows = {m._meta.label: m.objects.using(connection.alias).count() for m in models}
    rows[PARTIAL_LABEL + ' (linked only)'] = partial.objects.using(connection.alias).filter(reservation_id__isnull=False).count()
    rows['admin.LogEntry (reservation records only)'] = admin_scope(connection).count()
    return rows


def reset_rows(connection):
    """Caller owns the transaction and backup. Deliberately bypass save/delete signals."""
    from django.apps import apps
    models, partial = models_and_guard(connection)
    q = connection.ops.quote_name
    admin_ids = list(admin_scope(connection).values_list('pk', flat=True))
    # QuerySet delete here only touches admin logs, which have no booking hooks.
    if admin_ids:
        from django.contrib.admin.models import LogEntry
        LogEntry.objects.using(connection.alias).filter(pk__in=admin_ids).delete()
    with connection.cursor() as cursor:
        reservation = apps.get_model('bookings.Reservation')
        cursor.execute(f'UPDATE {q(reservation._meta.db_table)} SET {q("deposit_request_id")} = NULL WHERE {q("deposit_request_id")} IS NOT NULL')
        cursor.execute(f'DELETE FROM {q(partial._meta.db_table)} WHERE {q("reservation_id")} IS NOT NULL')
        for model in models:
            cursor.execute(f'DELETE FROM {q(model._meta.db_table)}')
    remaining = counts(connection)
    if any(remaining.values()):
        raise RuntimeError('Reset verification failed; transaction will roll back.')


def pg_environment(connection):
    params = connection.get_connection_params()
    # No passwords or credential-bearing DSNs in the subprocess argument list.
    env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    mapping = {'dbname': 'PGDATABASE', 'user': 'PGUSER', 'password': 'PGPASSWORD',
               'host': 'PGHOST', 'port': 'PGPORT', 'sslmode': 'PGSSLMODE',
               'sslcert': 'PGSSLCERT', 'sslkey': 'PGSSLKEY', 'sslrootcert': 'PGSSLROOTCERT'}
    for source, dest in mapping.items():
        if source in params:
            env[dest] = str(params[source])
        elif dest in env:
            del env[dest]
    env['PGCONNECT_TIMEOUT'] = '15'
    env['PGAPPNAME'] = 'summitdesk-reservation-reset-backup'
    return env


def run_pg(args, env):
    # Do not print stderr or environment: custom DSNs may contain credentials.
    result = subprocess.run(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    if result.returncode:
        raise RuntimeError(f'{Path(args[0]).name} failed (exit {result.returncode}); no successful reset is reported.')
    return result.stdout


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def applied_migrations(connection):
    from django.db.migrations.recorder import MigrationRecorder
    return [list(item) for item in sorted(MigrationRecorder(connection).applied_migrations())]


def target_identity(connection):
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(), current_user, inet_server_addr()::text, inet_server_port()')
        return list(cursor.fetchone())


def lock_database(connection):
    q = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '15s'")
        tables = sorted(connection.introspection.table_names(cursor))
        # SHARE ROW EXCLUSIVE blocks writes but permits pg_dump's ACCESS SHARE.
        cursor.execute('LOCK TABLE ' + ', '.join(q(t) for t in tables) + ' IN SHARE ROW EXCLUSIVE MODE')


def preflight(connection):
    if connection.vendor != 'postgresql':
        raise RuntimeError('This maintenance tool requires the production PostgreSQL settings.')
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise RuntimeError('Unapplied migrations found; reset refused.')
    for command in ('pg_dump', 'pg_restore'):
        if not shutil.which(command):
            raise RuntimeError(f'{command} is required before any data can be removed.')
    return counts(connection)


def execute_reset(root, connection):
    from django.db import transaction
    parent = root / 'summitdesk_backups'
    parent.mkdir(mode=0o700, exist_ok=True)
    if parent.is_symlink():
        raise RuntimeError('Backup directory must not be a symlink.')
    directory = parent / ('reservation_reset_v182_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    directory.mkdir(mode=0o700)
    dump = directory / 'database.dump'
    manifest = directory / 'manifest.json'
    env = pg_environment(connection)
    committed = False
    try:
        with transaction.atomic(using=connection.alias):
            lock_database(connection)
            before = counts(connection)
            identity = target_identity(connection)
            # All table writes are blocked until commit; pg_dump may still read.
            # Keep READ COMMITTED so pre-lock writes are visible to the deletion.
            run_pg(['pg_dump', '--format=custom', '--no-owner', '--no-privileges',
                    '--file=' + str(dump)], env)
            os.chmod(dump, 0o600)
            listing = run_pg(['pg_restore', '--list', str(dump)], env)
            if dump.stat().st_size < 100 or b'TABLE DATA' not in listing:
                raise RuntimeError('Backup archive is incomplete; no rows removed.')
            with open(dump, 'rb') as stream:
                os.fsync(stream.fileno())
            metadata = {'format': 'summitdesk-reset-v182', 'target': identity,
                        'created_utc': datetime.now(timezone.utc).isoformat(),
                        'database_sha256': sha256(dump), 'removed_rows': before,
                        'migrations': applied_migrations(connection)}
            manifest.write_text(json.dumps(metadata, indent=2) + '\n')
            os.chmod(manifest, 0o600)
            with open(manifest, 'rb') as stream:
                os.fsync(stream.fileno())
            for durable_dir in (directory, parent):
                descriptor = os.open(durable_dir, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            print(f'Backup: {directory}', flush=True)
            reset_rows(connection)
            connection.check_constraints()
        committed = True
    finally:
        if not committed:
            print('Reset did not complete. Database transaction rolled back; any backup was retained.', file=sys.stderr)
    print('Reset complete: all reservations and listed linked records are zero. No emails were sent.')
    print('Huts, rooms, beds, staff, settings, expenses, closures and standalone housekeeping retained.')
    print(f'Restore: bash v182_reservation_reset_package/reset_v182.sh --restore {directory}')


def validate_restore(root, directory, connection):
    directory = Path(directory).resolve(strict=True)
    parent = (root / 'summitdesk_backups').resolve(strict=True)
    if directory.parent != parent or not directory.name.startswith('reservation_reset_v182_'):
        raise RuntimeError('Restore accepts only a v182 reset backup in this project.')
    dump = directory / 'database.dump'
    manifest = directory / 'manifest.json'
    if dump.is_symlink() or manifest.is_symlink():
        raise RuntimeError('Symlinked backup files are refused.')
    metadata = json.loads(manifest.read_text())
    if metadata.get('format') != 'summitdesk-reset-v182' or metadata.get('target') != target_identity(connection):
        raise RuntimeError('Backup target does not match this database and role.')
    if metadata.get('migrations') != applied_migrations(connection):
        raise RuntimeError('Database migrations changed since this backup; restore refused.')
    if sha256(dump) != metadata.get('database_sha256'):
        raise RuntimeError('Backup checksum mismatch. Restore refused.')
    env = pg_environment(connection)
    run_pg(['pg_restore', '--list', str(dump)], env)
    return dump, env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--preview', action='store_true')
    group.add_argument('--execute', action='store_true')
    group.add_argument('--restore', metavar='BACKUP_DIRECTORY')
    group.add_argument('--check-restore', metavar='BACKUP_DIRECTORY')
    parser.add_argument('--project-root', default=str(Path.cwd()))
    parser.add_argument('--maintenance-stopped', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    root = configure(args.project_root)
    from django.db import connection
    before = preflight(connection)
    if args.restore or args.check_restore:
        dump, env = validate_restore(root, args.restore or args.check_restore, connection)
        if args.check_restore:
            print('Full database restore archive and target verified.')
            return
        if not args.maintenance_stopped:
            raise RuntimeError('Use reset_v182.sh --restore so writers are stopped first.')
        connection.close()
        run_pg(['pg_restore', '--clean', '--if-exists', '--no-owner', '--no-privileges',
                '--single-transaction', '--exit-on-error', '--dbname=' + env['PGDATABASE'], str(dump)], env)
        print('Full database restored. This also replaces all changes made after the backup.')
    elif args.execute:
        if not args.maintenance_stopped:
            raise RuntimeError('Use reset_v182.sh --execute so writers are stopped first.')
        execute_reset(root, connection)
    else:
        print('PREVIEW ONLY — no data changed. Records that will be removed across ALL huts:')
        for name, number in before.items():
            print(f'  {name}: {number}')
        print('Keeps: huts, rooms, beds, floor plans, photos, staff accounts, settings, policies,')
        print('expenses, bed closures, standalone housekeeping, login/rate limits and mailbox sync position.')
        print('Old guest reservation links will stop working. Database IDs will not be reused.')
        print('Execute with: bash v182_reservation_reset_package/reset_v182.sh --execute')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Reservation reset stopped: {type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
