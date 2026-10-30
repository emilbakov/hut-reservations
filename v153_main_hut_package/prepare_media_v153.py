#!/usr/bin/env python3
"""Copy referenced public hut photos safely; retain originals for source rollback."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def bounded(root, name):
    relative = PurePosixPath(name)
    if (not name.startswith('huts/') or '\\' in name or relative.is_absolute()
            or '..' in relative.parts or len(relative.parts) < 2):
        raise RuntimeError('Unsafe hut photo path; no files copied.')
    root = root.resolve()
    candidate = root.joinpath(*relative.parts)
    if root not in candidate.resolve().parents:
        raise RuntimeError('Hut photo path escapes its directory; no files copied.')
    current = candidate
    while current != root:
        if current.is_symlink():
            raise RuntimeError('Symlink in hut photo path; no files copied.')
        current = current.parent
    return candidate


def copy_photos(names, sources, destination, *, dry_run=False):
    plans = []
    for name in sorted(set(names)):
        if not name:
            continue
        target = bounded(destination, name)
        available = [bounded(root, name) for root in sources]
        available = [path for path in available if path.is_file()]
        if target.is_file():
            if any(digest(path) != digest(target) for path in available):
                raise RuntimeError('Different files share a hut photo path; no files copied: ' + name)
            continue
        if target.exists() or not available:
            raise RuntimeError('Referenced hut photo is missing or destination is not a file: ' + name)
        original = available[0]
        if any(digest(path) != digest(original) for path in available[1:]):
            raise RuntimeError('Conflicting original hut photos; no files copied: ' + name)
        plans.append((original, target))
    if dry_run:
        return len(plans)
    for original, target in plans:
        missing, parent = [], target.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            try:
                directory.mkdir(mode=0o755)
            except FileExistsError:
                if not directory.is_dir():
                    raise
            else:
                directory.chmod(0o755)
        # Exclusive creation never replaces a concurrently uploaded file.
        with original.open('rb') as source:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            try:
                with os.fdopen(descriptor, 'wb') as output:
                    os.fchmod(output.fileno(), 0o644)
                    shutil.copyfileobj(source, output)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
    return len(plans)


def nginx_snippet(root):
    # Refuse interpolated nginx variables and quoting instead of guessing at them.
    value = str(Path(root))
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', value):
        raise RuntimeError('Generate the nginx alias manually for this media path; see MEDIA_SETUP.md.')
    return '''# Add inside this site's application-serving server block.
location ^~ /media/ {
    alias %s/;
    autoindex off;
    add_header X-Content-Type-Options nosniff always;
    limit_except GET HEAD { deny all; }
}
''' % value.rstrip('/')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', action='store_true')
    parser.add_argument('--nginx-snippet', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(Path.cwd()))
    import django
    django.setup()
    from django.conf import settings
    if args.root:
        print(settings.MEDIA_ROOT)
        return
    if args.nginx_snippet:
        print(nginx_snippet(settings.MEDIA_ROOT), end='')
        return
    from bookings.models import Hut
    copied = copy_photos(
        Hut.objects.exclude(image='').values_list('image', flat=True),
        [Path(settings.BASE_DIR), Path(settings.BASE_DIR) / 'media'],
        Path(settings.MEDIA_ROOT), dry_run=args.dry_run,
    )
    print(('Would copy' if args.dry_run else 'Copied'), copied, 'hut photo(s). Original files retained.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
