#!/usr/bin/env python3
"""Install SummitDesk staff sign-in. No database changes.

Run from the Django project root. Existing files are backed up and all
writes are atomic. The installer refuses an already-installed release.
"""
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent

URLS = 'bookings/urls.py'
SETTINGS = 'config/settings.py'
LANDING = 'bookings/templates/bookings/role_landing.html'
BASE = 'bookings/templates/bookings/base.html'
NAV = 'floorplans/templates/floorplans/includes/summitdesk_nav.html'
NEW_FILES = {
    'bookings/staff_auth_v117.py': 'staff_auth_v117.py',
    'bookings/templates/bookings/staff_login.html': 'staff_login.html',
    'bookings/static/bookings/staff_login_v117.css': 'staff_login.css',
    'bookings/test_staff_auth_v117.py': 'test_staff_auth_v117.py',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def replace_exact(source, old, new, label, count=1):
    require(source.count(old) == count,
            f'{label}: expected {count} matching anchor(s), found {source.count(old)}. No files changed.')
    return source.replace(old, new)


def patch_urls(source):
    source = replace_exact(source, 'from . import views\n',
        'from . import views\nfrom .staff_auth_v117 import StaffLoginView, StaffLogoutView\n', URLS)
    source = replace_exact(source, 'urlpatterns = [\n',
        'urlpatterns = [\n'
        '    path("staff/login/", StaffLoginView.as_view(), name="staff_login"),\n'
        '    path("staff/logout/", StaffLogoutView.as_view(), name="staff_logout"),\n', URLS)
    return source


def patch_settings(source):
    source = replace_exact(source,
        '    "django.contrib.auth.middleware.AuthenticationMiddleware",',
        '    "django.contrib.auth.middleware.AuthenticationMiddleware",\n'
        '    "bookings.staff_auth_v117.StaffLoginRedirectMiddleware",', SETTINGS)
    require('LOGIN_URL =' not in source, 'LOGIN_URL already configured; review manually before installing.')
    return source.rstrip() + '\n\n# Staff and cleaner authentication entry point.\nLOGIN_URL = "/staff/login/"\n'


def patch_landing(source):
    source = replace_exact(source,
        "{% url 'admin:login' %}?next={% url 'bookings:dashboard' %}",
        "{% url 'bookings:staff_login' %}", LANDING)
    source = replace_exact(source,
        '<h2 id="manager-title">Hut Manager</h2>',
        '<h2 id="manager-title">Staff &amp; management</h2>', LANDING)
    source = replace_exact(source,
        'Manage bookings, guest arrivals, rooms, availability and payments from one workspace.',
        'Managers and housekeeping teams: sign in to manage bookings, arrivals, rooms and daily tasks.', LANDING)
    source = replace_exact(source, 'Manager login →', 'Staff sign in →', LANDING)
    return source


def patch_base(source):
    anchor = '<a href="{% url \'bookings:hut_list\' %}#how-it-works">How it works</a>'
    return replace_exact(source, anchor,
        anchor + '\n        <a href="{% url \'bookings:staff_login\' %}">Staff sign in</a>',
        BASE, count=2)


def patch_nav(source):
    old = '<div class="sd116-sidebar-bottom"><a href="{{ public_url }}">↗ &nbsp; Open public website</a><span>SummitDesk · Staff workspace</span></div>'
    new = '''<div class="sd116-sidebar-bottom">
    <a href="{{ public_url }}">↗ &nbsp; Open public website</a>
    <form method="post" action="{% url 'bookings:staff_logout' %}" class="sd117-signout-form">
      {% csrf_token %}
      <button type="submit" class="sd117-signout-button">↪ &nbsp; Sign out</button>
    </form>
    <span>SummitDesk · Staff workspace</span>
  </div>
  <style>
    .sd117-signout-form{margin:0!important;padding:0!important}
    .sd117-signout-button{border:0!important;background:transparent!important;padding:0!important;margin:0!important;color:#d6f2ae!important;font:700 13px/1.5 system-ui,sans-serif!important;cursor:pointer!important;text-align:left!important;box-shadow:none!important}
    .sd117-signout-button:hover{text-decoration:underline!important}
    .sd117-signout-button:focus-visible{outline:3px solid #b6e57d!important;outline-offset:4px!important}
  </style>'''
    return replace_exact(source, old, new, NAV)


def atomic_write(target, content):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.sd117_',
                                         dir=target.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(content)
        os.chmod(temp, (target.stat().st_mode & 0o777) if target.exists() else 0o644)
        os.replace(temp, target)
    finally:
        if temp and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file() and (ROOT / URLS).is_file(),
            'Run this installer from the SummitDesk Django project directory.')
    require((ROOT / 'floorplans/static/floorplans/summitdesk_shell_v116.css').is_file(),
            'The v116 shared staff layout must be installed first.')
    for relative in [URLS, SETTINGS, LANDING, BASE, NAV]:
        require((ROOT / relative).is_file(), f'Missing required file: {relative}')
    for relative in NEW_FILES:
        require(not (ROOT / relative).exists(),
                f'Already installed or partial installation: {relative}. Refusing to overwrite.')
    require('sd116-sidebar-bottom' in (ROOT / NAV).read_text(encoding='utf-8'),
            'The expected shared navigation is missing.')

    changes = {}
    for relative, patch in ((URLS, patch_urls), (SETTINGS, patch_settings),
                            (LANDING, patch_landing), (BASE, patch_base), (NAV, patch_nav)):
        changes[relative] = patch((ROOT / relative).read_text(encoding='utf-8')).encode('utf-8')
    for relative, filename in NEW_FILES.items():
        require((PKG / filename).is_file(), f'Package file missing: {filename}')
        changes[relative] = (PKG / filename).read_bytes()
    for relative, content in changes.items():
        require(not (ROOT / relative).is_symlink(), f'Refusing to replace symlink: {relative}')
        if relative.endswith('.py'):
            ast.parse(content.decode('utf-8'), filename=relative)
    require(b'{% csrf_token %}' in changes[NAV], 'Sign-out form must use CSRF protection.')
    require(b'{% csrf_token %}' in changes['bookings/templates/bookings/staff_login.html'],
            'Login form must use CSRF protection.')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('staff_login_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for relative in changes:
        original = ROOT / relative
        existed = original.is_file()
        manifest.append({'path': relative, 'existed': existed})
        if existed:
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for relative, content in changes.items():
            atomic_write(ROOT / relative, content)
    except Exception:
        for entry in manifest:
            target = ROOT / entry['path']
            if entry['existed']:
                shutil.copy2(backup / entry['path'], target)
            else:
                target.unlink(missing_ok=True)
        raise
    print('SummitDesk staff sign-in installed.')
    print('Backup:', backup)
    print('No migrations. Run manage.py check, collectstatic and the focused tests.')


if __name__ == '__main__':
    main()
