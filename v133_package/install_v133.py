#!/usr/bin/env python3
"""Install SummitDesk v133 mobile staff UI without changing booking logic.

Run beside manage.py: python3 v133_package/install_v133.py
No Django imports, database writes, or external calls.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent
JS_SHA_V132 = '6b6b6976046ed1458871fc4a1411bb2e2c4c73f078d78bdd7c5e5ed40acd229f'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def target_path(rel):
    path = Path(rel)
    require(not path.is_absolute() and '..' not in path.parts, f'Unsafe path: {rel}')
    target = ROOT / path
    require(ROOT in target.parents, f'Outside project: {rel}')
    require(not target.is_symlink(), f'Symlink target refused: {rel}')
    current = target.parent
    while current != ROOT:
        require(not current.is_symlink(), f'Symlink directory refused: {current}')
        current = current.parent
    return target


def replace_once(source, before, after, label):
    count = source.count(before)
    require(count == 1, f'Unexpected {label}: expected one anchor, found {count}. No files changed.')
    return source.replace(before, after, 1)


def inject_css(source, css_name, label):
    css = (PKG / css_name).read_text(encoding='utf-8').strip()
    require('/* v133:' not in source, f'{label} appears already upgraded; refusing overwrite.')
    return replace_once(source, '</style>', '\n' + css + '\n</style>', label + ' style block')


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd133_', delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def build_payload():
    require((ROOT / 'manage.py').is_file(), 'Run from Django project root beside manage.py.')
    require((ROOT / 'bookings/manager_digest_history_v132.py').is_file(), 'Install v132 first.')
    require((ROOT / 'bookings/approval_dashboard_v127.py').is_file(), 'v127 guest request dashboard is missing.')

    reservations_rel = 'bookings/templates/bookings/manager_reservations.html'
    requests_rel = 'bookings/templates/bookings/approval_dashboard_v127.html'
    dashboard_rel = 'bookings/templates/bookings/dashboard.html'
    calendar_rel = 'bookings/templates/bookings/calendar_timeline.html'
    shell_css_rel = 'floorplans/static/floorplans/summitdesk_shell_v116.css'
    shell_js_rel = 'floorplans/static/floorplans/summitdesk_shell_v116.js'
    nav_rel = 'floorplans/templatetags/summitdesk_nav.py'

    reservations = target_path(reservations_rel).read_text(encoding='utf-8')
    for before, after, label in [
        ('<td><div class="mr-guest">', '<td data-label="Guest"><div class="mr-guest">', 'guest cell'),
        ('<td>{% for item in reservation.items.all %}', '<td data-label="Hut">{% for item in reservation.items.all %}', 'hut cell'),
        ('<td class="mr-dates">', '<td class="mr-dates" data-label="Stay dates">', 'dates cell'),
        ('<td><span class="mr-beds">', '<td data-label="Beds"><span class="mr-beds">', 'beds cell'),
        ('<td><span class="mr-status ', '<td data-label="Status"><span class="mr-status ', 'status cell'),
        ('<td><div class="mr-actions">', '<td data-label="Actions"><div class="mr-actions">', 'actions cell'),
    ]:
        reservations = replace_once(reservations, before, after, label)
    reservations = inject_css(reservations, 'reservations_mobile.css', 'reservations')

    requests = inject_css(target_path(requests_rel).read_text(encoding='utf-8'), 'requests_mobile.css', 'requests')
    dashboard = inject_css(target_path(dashboard_rel).read_text(encoding='utf-8'), 'dashboard_mobile.css', 'dashboard')
    calendar = target_path(calendar_rel).read_text(encoding='utf-8')
    calendar = replace_once(
        calendar,
        '<div class="sd-board" role="region"',
        '<p class="sd-mobile-scroll-hint" id="sd-mobile-scroll-hint">↔ Swipe sideways to view the full week.</p>\n'
        '<div class="sd-board" role="region"',
        'calendar swipe hint',
    )
    calendar = inject_css(calendar, 'calendar_mobile.css', 'calendar')

    shell_css = target_path(shell_css_rel).read_text(encoding='utf-8')
    require('/* v133:' not in shell_css, 'Mobile shell CSS already installed.')
    shell_css += '\n' + (PKG / 'shell_mobile.css').read_text(encoding='utf-8')

    shell_js_path = target_path(shell_js_rel)
    old_js = shell_js_path.read_bytes()
    require(hashlib.sha256(old_js).hexdigest() == JS_SHA_V132,
            'Mobile navigation JavaScript differs from v132; refusing to overwrite customized JS.')
    new_js = (PKG / 'summitdesk_shell_v133.js').read_bytes()

    nav = target_path(nav_rel).read_text(encoding='utf-8')
    nav = replace_once(
        nav,
        "    'guest_requests_dashboard', 'guest_link_controls',\n",
        "    'guest_requests_dashboard', 'guest_link_controls',\n"
        "    'approval_dashboard', 'manager_digest_preferences',\n"
        "    'manager_digest_preview', 'manager_digest_history',\n",
        'staff shell route allowlist',
    )
    nav = replace_once(
        nav,
        "    'guest_link_controls': 'guests',\n",
        "    'guest_link_controls': 'guests',\n"
        "    'approval_dashboard': 'approvals',\n"
        "    'manager_digest_preferences': 'reminders',\n"
        "    'manager_digest_preview': 'reminders',\n"
        "    'manager_digest_history': 'reminders',\n",
        'staff shell section mapping',
    )
    nav = replace_once(
        nav,
        "            b('communications_dashboard', 'Guest communication', 'messages-square', 'guests'),\n",
        "            b('communications_dashboard', 'Guest communication', 'messages-square', 'guests'),\n"
        "            b('approval_dashboard', 'Guest approvals', 'clipboard-list', 'approvals'),\n"
        "            b('manager_digest_preferences', 'Reminder settings', 'mail', 'reminders'),\n",
        'staff shell business links',
    )
    compile(nav, nav_rel, 'exec')

    test_rel = 'bookings/test_mobile_v133.py'
    require(not target_path(test_rel).exists(), 'v133 test file already exists; refusing overwrite.')
    test_bytes = (PKG / 'test_mobile_v133.py').read_bytes()
    compile(test_bytes, test_rel, 'exec')

    return {
        reservations_rel: reservations.encode('utf-8'),
        requests_rel: requests.encode('utf-8'),
        dashboard_rel: dashboard.encode('utf-8'),
        calendar_rel: calendar.encode('utf-8'),
        shell_css_rel: shell_css.encode('utf-8'),
        shell_js_rel: new_js,
        nav_rel: nav.encode('utf-8'),
        test_rel: test_bytes,
    }


def main():
    payload = build_payload()  # All preflight checks happen before any file changes.
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'mobile_v133_{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel, data in payload.items():
        target = target_path(rel)
        existed = target.is_file()
        manifest.append({'path': rel, 'existed': existed,
                         'installed_sha256': hashlib.sha256(data).hexdigest()})
        if existed:
            saved = backup / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for rel, data in payload.items():
            atomic_write(target_path(rel), data)
    except Exception:
        for entry in manifest:
            target = target_path(entry['path'])
            if entry['existed']:
                shutil.copy2(backup / entry['path'], target)
            elif target.exists():
                target.unlink()
        raise
    print('SummitDesk v133 installed: responsive staff reservations, requests, dashboard and calendar.')
    print('Mobile drawer keyboard focus, touch targets and scroll behavior improved.')
    print('Backup:', backup)
    print('No database migrations required. Run targeted tests and collectstatic before restart.')


if __name__ == '__main__':
    main()
