#!/usr/bin/env python3
"""Check the unchanged project settings without Django or printing secrets."""
from pathlib import Path
import runpy
import sys


def validate(project_root):
    # This incremental release does not replace config/settings.py. Evaluate the
    # installed settings so both the source path and BASE_DIR match production.
    root = Path(project_root).resolve()
    settings_file = root / 'config/settings.py'
    if not settings_file.is_file():
        raise RuntimeError('Missing project config/settings.py. Run from the project directory beside manage.py.')
    values = runpy.run_path(str(settings_file))
    if values['DEBUG']:
        raise RuntimeError('Production has DJANGO_DEBUG=1. Set DJANGO_DEBUG=0 in /etc/hut-reservations/postgres.env before installing.')
    if values['SECRET_KEY'] in {
        'test-only-not-secret', 'test-only-not-a-production-secret',
        'v145-isolated-tests-only-not-a-production-secret-key',
    }:
        raise RuntimeError('A test-only secret is configured. Restore the real production DJANGO_SECRET_KEY before installing.')
    media = Path(values['MEDIA_ROOT']).resolve()
    if media == Path('/') or media == root or root in media.parents or media in root.parents:
        raise RuntimeError('DJANGO_MEDIA_ROOT must be a dedicated directory outside the application, not an ancestor of it.')


if __name__ == '__main__':
    try:
        validate(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd())
    except (RuntimeError, ValueError, OSError) as exc:
        raise SystemExit(str(exc))
    print('v181 production environment passed. No secret values were printed or changed.')
