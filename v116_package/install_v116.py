#!/usr/bin/env python3
"""Install the shared SummitDesk management shell, with full rollback.

No database migrations, URL changes or model/view changes. Requires v115.
Run from the Django project root.
"""
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent
BASE = 'bookings/templates/bookings/base.html'
TAG = 'floorplans/templatetags/summitdesk_nav.py'
INCLUDE = 'floorplans/templates/floorplans/includes/summitdesk_nav.html'
CSS = 'floorplans/static/floorplans/summitdesk_shell_v116.css'
JS = 'floorplans/static/floorplans/summitdesk_shell_v116.js'
STANDALONE = [
    'cleaner_invitations', 'cleaner_portal', 'cleaner_team',
    'manager_operations_v63_v67', 'staff_analytics', 'staff_arrivals',
    'staff_audit_dashboard', 'staff_calendar', 'staff_financial_analytics',
    'staff_history', 'staff_housekeeping', 'staff_hub', 'staff_new_booking',
    'staff_overview', 'staff_reservation', 'staff_search', 'staff_tasks',
    'staff_transfer',
]


def stop(message):
    sys.exit('ERROR: ' + message + ' No files changed.')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected exactly one match for ' + repr(old[:65]))
    return text.replace(old, new, 1)


def patch_base(text):
    if 'sd116_staff_area' in text:
        raise ValueError('Shared staff shell already installed.')
    if 'sd115-nav' not in text or 'adventure-footer' not in text:
        raise ValueError('Expected v115 bookings base not found.')
    text = replace_once(text, '{% load static %}',
                        '{% load static summitdesk_nav %}\n{% sd116_staff_area as sd116_staff %}')
    text = replace_once(text, '<body>', '<body{% if sd116_staff %} class="sd116-active"{% endif %}>')
    text = replace_once(text, '  <a class="skip-link" href="#main-content">Skip to content</a>',
                        '  {% if not sd116_staff %}<a class="skip-link" href="#main-content">Skip to content</a>{% endif %}')
    text = replace_once(text, '  <header class="site-header adventure-header">',
                        '  {% if sd116_staff %}{% summitdesk_nav %}{% else %}\n  <header class="site-header adventure-header">')
    text = replace_once(text, '  </header>\n  <main id="main-content" class="shell">',
                        '  </header>\n  {% endif %}\n  <main id="main-content" class="shell">')
    text = replace_once(text, '  <footer class="site-footer adventure-footer">',
                        '  {% if not sd116_staff %}<footer class="site-footer adventure-footer">')
    text = replace_once(text, '  </footer>\n</body>', '  </footer>{% endif %}\n</body>')
    return text


def patch_staff_template(text, name):
    if 'sd116-active' in text:
        raise ValueError(name + ' already has the staff shell.')
    text = replace_once(text, '<body>', '<body class="sd116-active">')
    if '{% summitdesk_nav %}' not in text:
        text = '{% load summitdesk_nav %}\n' + text
        text = replace_once(text, '<body class="sd116-active">',
                            '<body class="sd116-active">{% summitdesk_nav %}')
    if '<main' not in text:
        raise ValueError(name + ' has no main content region.')
    if 'id="main-content"' not in text:
        text = replace_once(text, '<main', '<main id="main-content"')
    if name == 'staff_financial_analytics':
        text = text.replace('SummitDesk v35', 'SummitDesk')
    if name == 'staff_audit_dashboard':
        text = text.replace('Events recorded since V31 installation.',
                            'Events recorded since audit tracking was enabled.')
    if name == 'staff_history':
        text = text.replace('Audit events begin at V31 installation. V32 adds field comparisons and request actor tracking; older events remain unchanged.',
                            'Audit history covers recorded events since tracking was enabled; older events remain unchanged.')
    return text


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent,
                                         prefix='.sd116_', delete=False) as fh:
            fh.write(data)
            tmp = Path(fh.name)
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o777)
        else:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def main():
    if not (ROOT / 'manage.py').is_file() or not (ROOT / 'bookings/urls.py').is_file():
        stop('Run from the SummitDesk Django project root.')
    required = [BASE, TAG, INCLUDE] + [f'floorplans/templates/floorplans/{n}.html' for n in STANDALONE]
    if any(not (ROOT / path).is_file() for path in required):
        stop('Missing one or more required staff templates or navigation files.')
    if (ROOT / CSS).exists() or (ROOT / JS).exists():
        stop('Static shell files already exist. Check for an earlier or partial installation.')

    changes = {}
    try:
        changes[BASE] = patch_base((ROOT / BASE).read_text(encoding='utf-8')).encode('utf-8')
        for name in STANDALONE:
            path = f'floorplans/templates/floorplans/{name}.html'
            changes[path] = patch_staff_template((ROOT / path).read_text(encoding='utf-8'), name).encode('utf-8')
        if 'sd116' in (ROOT / TAG).read_text(encoding='utf-8'):
            raise ValueError('Navigation tag already updated.')
        ast.parse((PKG / 'summitdesk_nav.py').read_text(encoding='utf-8'))
        changes[TAG] = (PKG / 'summitdesk_nav.py').read_bytes()
        changes[INCLUDE] = (PKG / 'summitdesk_nav.html').read_bytes()
        changes[CSS] = (PKG / 'summitdesk_shell.css').read_bytes()
        changes[JS] = (PKG / 'summitdesk_shell.js').read_bytes()
        if 'sd116-sidebar' not in changes[INCLUDE].decode() or 'sd116-menu-open' not in changes[JS].decode():
            raise ValueError('Incomplete package.')
    except (ValueError, SyntaxError) as exc:
        stop(str(exc))

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('shared_shell_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for relative in changes:
        original = ROOT / relative
        existed = original.is_file()
        manifest.append({'path': relative, 'existed': existed})
        if existed:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, saved)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    try:
        for relative, data in changes.items():
            atomic_write(ROOT / relative, data)
    except Exception:
        for item in manifest:
            target = ROOT / item['path']
            if item['existed']:
                shutil.copy2(backup / item['path'], target)
            else:
                target.unlink(missing_ok=True)
        raise
    print('Installed shared SummitDesk front-desk navigation across staff pages.')
    print('Backups:', backup)
    print('No database migrations. Run manage.py check and collectstatic before restarting.')


if __name__ == '__main__':
    main()
