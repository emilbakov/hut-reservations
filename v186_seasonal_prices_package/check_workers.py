"""Refuse unmanaged writers after systemd/cron are paused; do not kill them."""
import os
from pathlib import Path
import sys
root = str(Path.cwd().resolve())
blocked = []
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit() or int(entry.name) == os.getpid():
        continue
    try:
        args = (entry / 'cmdline').read_bytes().replace(b'\x00', b' ').decode(errors='replace')
        cwd = str((entry / 'cwd').resolve(strict=True))
    except (OSError, PermissionError):
        continue
    if root not in args and not (cwd == root or cwd.startswith(root + '/')):
        continue
    if any(word in args for word in ('manage.py', 'gunicorn', 'celery', 'rqworker', 'reset_reservations.py')):
        blocked.append(entry.name)
if blocked:
    print('Unmanaged application workers still running (PIDs only): ' + ', '.join(blocked), file=sys.stderr)
    print('No reset performed. Stop these project jobs and rerun.', file=sys.stderr)
    sys.exit(1)
print('Application worker check passed.')
