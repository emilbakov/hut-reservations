#!/usr/bin/env python3
"""One-template staff booking redesign. Run from SummitDesk Django root.

Preflight all inputs before modifying files, make a timestamped backup,
then install atomically. No migrations and no changes to booking services.
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
PROPERTY = 'floorplans/staff_new_booking.py'
HELPER = 'bookings/staff_booking_ui_v121.py'
TEMPLATE = 'bookings/templates/bookings/staff_booking_v121.html'
TESTS = 'bookings/test_staff_booking_ui_v121.py'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def once(source, old, new, file):
    count = source.count(old)
    require(count == 1, f'{file}: expected one known anchor; found {count}. Nothing installed.')
    return source.replace(old, new)


def patch_manual(source):
    require('@login_required(login_url="/staff/login/")' in source,
            'v118 manager-access fix is required before installing.')
    source = once(source,
        'from .services import NotAvailable, create_reservation, free_beds',
        'from .services import NotAvailable, create_reservation, free_beds\nfrom .staff_booking_ui_v121 import availability_summary', MANUAL)
    source = once(source,
        '''    if date_form_valid:
        start, end = form.cleaned_data["check_in"], form.cleaned_data["check_out"]
    elif request.method == "GET":''',
        '''    if date_form_valid:
        start, end = form.cleaned_data["check_in"], form.cleaned_data["check_out"]
    elif request.method == "POST":
        # Keep showing availability and entered guest details when POST validation
        # fails (e.g. missing contact or a room quantity error).
        try:
            start = forms.DateField().clean(request.POST.get("check_in"))
            end = forms.DateField().clean(request.POST.get("check_out"))
            today = timezone.localdate()
            if (start < today or end <= start or
                start > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD) or
                (end-start).days > settings.BOOKING_MAX_NIGHTS):
                start = end = None
        except (forms.ValidationError, TypeError, ValueError):
            start = end = None
    elif request.method == "GET":''', MANUAL)
    source = once(source,
        '''            start = forms.DateField().clean(request.GET.get("check_in"))
            end = forms.DateField().clean(request.GET.get("check_out"))''',
        '''            start = forms.DateField().clean(request.GET.get("check_in") or timezone.localdate().isoformat())
            end = forms.DateField().clean(request.GET.get("check_out") or (timezone.localdate() + timedelta(days=1)).isoformat())''', MANUAL)
    source = once(source,
        'room_rows.append({"room": room, "free": free.get(room.pk), "requested": raw})',
        'room_rows.append({"room": room, "free": free.get(room.pk), "requested": raw,\n'
        '                          "unavailable": max(0, room.capacity - free.get(room.pk, 0))})', MANUAL)
    source = once(source,
        '''    return render(request, "bookings/manual_booking.html", {
        "form": form, "selected_hut": chosen, "room_rows": room_rows,
        "today": timezone.localdate(),
        "dates_ready": bool(start and end),
        "CURRENCY": settings.BOOKING_CURRENCY,
    })''',
        '''    today = timezone.localdate()
    return render(request, "bookings/staff_booking_v121.html", {
        "form": form, "selected_hut": chosen, "room_rows": room_rows,
        "booking_mode": "manual",
        "dates_action": "/staff/reservations/new/",
        "booking_action": "/staff/reservations/new/",
        "check_in_value": (request.POST.get("check_in") if request.method == "POST" else request.GET.get("check_in")) or today.isoformat(),
        "check_out_value": (request.POST.get("check_out") if request.method == "POST" else request.GET.get("check_out")) or (today + timedelta(days=1)).isoformat(),
        "today_iso": today.isoformat(),
        "availability": availability_summary(rooms, free, start, end),
        "currency": settings.BOOKING_CURRENCY,
        "date_error": ("Invalid dates. Check the booking horizon and stay length."
                       if ((request.GET.get("check_in") or request.GET.get("check_out"))
                           if request.method == "GET" else
                           (request.POST.get("check_in") or request.POST.get("check_out")))
                       and not (start and end) else None),
    })''', MANUAL)
    return source


def patch_property(source):
    require('@login_required(login_url="/staff/login/")' in source,
            'v118 manager-access fix is required before installing.')
    require('hut = permitted_hut(request, hut_id)' in source,
            'Property authorization guard missing.')
    source = once(source,
        'from bookings.services import NotAvailable, create_reservation, free_beds',
        'from bookings.services import NotAvailable, create_reservation, free_beds\nfrom bookings.staff_booking_ui_v121 import availability_summary', PROPERTY)
    source = once(source,
        '''    return render(request, "floorplans/staff_new_booking.html", {
        "hut": hut, "form": form, "rooms": rooms, "check_in": raw_start,
        "check_out": raw_end, "date_error": error, "valid_dates": valid_dates,
        "today": today.isoformat(),
    })''',
        '''    room_rows = []
    for room, available, field in form.rows():
        if field:
            form.fields[form.field_name(room)].widget.attrs["id"] = f"sd-bed-{room.pk}"
        room_rows.append({"room": room, "free": available, "field": field,
                          "unavailable": max(0, room.capacity - available)})
    return render(request, "bookings/staff_booking_v121.html", {
        "hut": hut, "selected_hut": hut, "form": form, "rooms": rooms,
        "room_rows": room_rows, "booking_mode": "property",
        "dates_action": request.path, "booking_action": request.path,
        "check_in_value": raw_start, "check_out_value": raw_end,
        "date_error": error or ("Invalid dates. Check the booking horizon and stay length."
                                if not valid_dates else None),
        "today_iso": today.isoformat(),
        "availability": availability_summary(rooms, free, start if valid_dates else None, end if valid_dates else None),
        "currency": settings.BOOKING_CURRENCY,
    })''', PROPERTY)
    return source


def atomic_write(path, data):
    temp = None
    try:
        with tempfile.NamedTemporaryFile('wb', prefix='.sd121_', dir=path.parent, delete=False) as f:
            temp = Path(f.name)
            f.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from the Django project root.')
    require((ROOT / 'floorplans/templatetags/summitdesk_nav.py').is_file(),
            'SummitDesk shared navigation must already be installed.')
    changes = {}
    for rel, patch in ((MANUAL, patch_manual), (PROPERTY, patch_property)):
        path = ROOT / rel
        require(path.is_file() and not path.is_symlink(), f'Missing or unsafe: {rel}')
        changes[rel] = patch(path.read_text(encoding='utf-8')).encode('utf-8')
    for rel in (HELPER, TEMPLATE, TESTS):
        require(not (ROOT / rel).exists(), f'{rel} already exists. Refusing to overwrite.')
        source = PKG / Path(rel).name
        require(source.is_file() and not source.is_symlink(), f'Missing package file: {source.name}')
        changes[rel] = source.read_bytes()
    for rel, data in changes.items():
        if rel.endswith('.py'):
            ast.parse(data.decode('utf-8'), filename=rel)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / ('booking_ui_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel in changes:
        path = ROOT / rel
        require(not path.is_symlink(), f'Symlink not allowed: {rel}')
        existed = path.is_file()
        manifest.append({'path': rel, 'existed': existed})
        if existed:
            target = backup / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    try:
        for rel, data in changes.items():
            path = ROOT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, data)
    except Exception:
        for entry in manifest:
            path = ROOT / entry['path']
            if entry['existed']:
                shutil.copy2(backup / entry['path'], path)
            else:
                path.unlink(missing_ok=True)
        raise
    print('Staff booking UI installed for both reservation URLs.')
    print('Backup:', backup)
    print('No migrations. Run Django checks and bookings.test_staff_booking_ui_v121.')


if __name__ == '__main__':
    main()
