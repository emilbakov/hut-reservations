#!/usr/bin/env python3
"""SummitDesk: fix New Booking 403 without expanding access to other huts.

Run from the Django project root after v116/v117. Preflight all anchors,
back up changed files, and atomically install. No migrations.
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
MANUAL = 'bookings/manual_bookings.py'
FLOOR = 'floorplans/staff_new_booking.py'
NAV = 'floorplans/templatetags/summitdesk_nav.py'
TEMPLATE = 'bookings/templates/bookings/manual_booking.html'
PROPERTY_TEMPLATE = 'floorplans/templates/floorplans/staff_new_booking.html'
TEST = 'bookings/test_booking_access_v118.py'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def replace_once(src, old, new, name):
    count = src.count(old)
    require(count == 1, f'{name}: expected one matching anchor, found {count}; no changes made.')
    return src.replace(old, new)


def patch_manual(src):
    src = replace_once(src,
        'from django.contrib.admin.views.decorators import staff_member_required',
        'from django.contrib.auth.decorators import login_required', MANUAL)
    src = replace_once(src, '@staff_member_required\ndef manual_booking(request):',
        '@login_required(login_url="/staff/login/")\ndef manual_booking(request):', MANUAL)
    src = replace_once(src,
        '''    if hut_id:
        # Never use a raw hut id without applying the authorized queryset.
        chosen = huts.filter(pk=hut_id).first() if str(hut_id).isdigit() else None
        if chosen is None:
            raise PermissionDenied("Hut not permitted.")''',
        '''    if hut_id:
        # Accept the numeric ID used by the booking form AND the slug used by
        # dashboard/sidebar links. Both must resolve inside the manager's
        # active, authorized huts. Never resolve globally then trust the result.
        hut_value = str(hut_id).strip()
        if request.method == "POST":
            # The form's ModelChoiceField is deliberately PK-based.
            chosen = huts.filter(pk=hut_value).first() if (hut_value.isascii() and hut_value.isdigit()) else None
        else:
            chosen = huts.filter(pk=hut_value).first() if (hut_value.isascii() and hut_value.isdigit()) else None
            if chosen is None:
                chosen = huts.filter(slug=hut_value).first()
        if chosen is None:
            raise PermissionDenied("Hut not permitted.")''', MANUAL)
    src = replace_once(src,
        '                return redirect("bookings:manager_reservations")',
        '''                # Global reservation management still requires is_staff;
                # hut managers without that flag return to their own workspace.
                if request.user.is_staff:
                    return redirect("bookings:manager_reservations")
                return redirect("floorplans:staff_hub", hut_id=chosen.pk)''', MANUAL)
    return src


def patch_floor(src):
    src = replace_once(src,
        'from django.contrib.admin.views.decorators import staff_member_required',
        'from django.contrib.auth.decorators import login_required', FLOOR)
    src = replace_once(src, '@staff_member_required\n@require_http_methods',
        '@login_required(login_url="/staff/login/")\n@require_http_methods', FLOOR)
    src = replace_once(src,
        '                return redirect("floorplans:staff_calendar", hut_id=hut.pk)',
        '                if request.user.is_staff:\n'
        '                    return redirect("floorplans:staff_calendar", hut_id=hut.pk)\n'
        '                return redirect("floorplans:staff_hub", hut_id=hut.pk)', FLOOR)
    # The existing permitted_hut() check remains in place and checks membership.
    require('hut = permitted_hut(request, hut_id)' in src,
            'Hut authorization guard missing from floorplan booking view.')
    return src


def patch_nav(src):
    # Only the booking buttons are made visible to assigned hut managers.
    src = replace_once(src,
        "            f('staff_calendar', 'Property calendar', 'calendar-range', 'property_calendar'),",
        "            f('staff_calendar', 'Property calendar', 'calendar-range', 'property_calendar'),\n"
        "            f('staff_new_booking', 'New reservation', 'plus-circle', 'new'),", NAV)
    src = replace_once(src,
        "        'new_booking_url': b('manual_booking', 'New reservation', 'plus-circle', 'new')['url'] if user.is_staff else None,",
        "        'new_booking_url': (b('manual_booking', 'New reservation', 'plus-circle', 'new')['url']\n"
        "                            if user.is_staff else\n"
        "                            f('staff_new_booking', 'New reservation', 'plus-circle', 'new')['url']\n"
        "                            if hut and manager else None),", NAV)
    return src


def patch_template(src):
    src = replace_once(src,
        '''  <p><a href="{% url 'bookings:dashboard' %}" class="mb-muted">← Back to dashboard</a></p>''',
        '''  <p>{% if request.user.is_staff %}<a href="{% url 'bookings:dashboard' %}" class="mb-muted">← Back to dashboard</a>{% elif selected_hut %}<a href="{% url 'floorplans:staff_hub' selected_hut.pk %}" class="mb-muted">← Back to hut dashboard</a>{% else %}<a href="{% url 'floorplans:staff_home' %}" class="mb-muted">← Back to my hut</a>{% endif %}</p>''', TEMPLATE)
    return src



def patch_property_template(src):
    src = replace_once(src,
        "<header><a href=\"{% url 'floorplans:staff_overview' hut.pk %}\">← Dashboard</a>",
        "<header><a href=\"{% if request.user.is_staff %}{% url 'floorplans:staff_overview' hut.pk %}{% else %}{% url 'floorplans:staff_hub' hut.pk %}{% endif %}\">← Dashboard</a>", PROPERTY_TEMPLATE)
    src = replace_once(src,
        "href=\"{% url 'floorplans:staff_calendar' hut.pk %}\">Cancel</a>",
        "href=\"{% if request.user.is_staff %}{% url 'floorplans:staff_calendar' hut.pk %}{% else %}{% url 'floorplans:staff_hub' hut.pk %}{% endif %}\">Cancel</a>", PROPERTY_TEMPLATE)
    return src


def atomic_write(path, data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('wb', prefix='.sd118_', dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        os.chmod(tmp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(tmp, path)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from the SummitDesk Django project root.')
    require((ROOT / 'bookings/staff_auth_v117.py').is_file(), 'Install staff login v117 first.')
    require((ROOT / NAV).is_file(), 'Install shared navigation v116 first.')
    changes = {}
    for rel, patch in ((MANUAL, patch_manual), (FLOOR, patch_floor),
                       (NAV, patch_nav), (TEMPLATE, patch_template),
                       (PROPERTY_TEMPLATE, patch_property_template)):
        path = ROOT / rel
        require(path.is_file() and not path.is_symlink(), f'Missing/unsafe file: {rel}')
        changes[rel] = patch(path.read_text(encoding='utf-8')).encode('utf-8')
    require(not (ROOT / TEST).exists(), 'Tests already installed: v118 may already be applied.')
    require((PKG / 'test_booking_access_v118.py').is_file(), 'Missing regression tests.')
    changes[TEST] = (PKG / 'test_booking_access_v118.py').read_bytes()
    for rel, data in changes.items():
        if rel.endswith('.py'):
            ast.parse(data.decode('utf-8'), filename=rel)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('booking_403_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel in changes:
        src = ROOT / rel
        existed = src.is_file()
        require(not src.is_symlink(), f'Symlink not allowed: {rel}')
        manifest.append({'path': rel, 'existed': existed})
        if existed:
            dst = backup / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for rel, data in changes.items():
            atomic_write(ROOT / rel, data)
    except Exception:
        for entry in manifest:
            target = ROOT / entry['path']
            if entry['existed']:
                shutil.copy2(backup / entry['path'], target)
            else:
                target.unlink(missing_ok=True)
        raise
    print('SummitDesk New Booking permission/link fix installed.')
    print('Backup:', backup)
    print('No migrations. Run Django checks and bookings.test_booking_access_v118.')


if __name__ == '__main__':
    main()
