#!/usr/bin/env python3
"""Install guest-approval workflow into SummitDesk v125.

Run from the Django project root. Creates backups before any file changes.
Database migration is a separate, explicit step after installation.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent

NEW_FILES = {
    'bookings/migrations/0013_reservation_guest_request.py': '0013_reservation_guest_request.py',
    'bookings/guest_requests_v126.py': 'guest_requests_v126.py',
    'bookings/templates/bookings/email_request_received_v126.txt': 'email_request_received_v126.txt',
    'bookings/templates/bookings/email_request_declined_v126.txt': 'email_request_declined_v126.txt',
    'bookings/test_guest_approval_v126.py': 'test_guest_approval_v126.py',
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def replace_one(text, old, new, label):
    require(text.count(old) == 1, f'Unexpected {label} structure (expected exactly one match). No files changed.')
    return text.replace(old, new, 1)


def patch_models(text):
    marker = 'class Reservation(models.Model):'
    next_marker = 'class ReservationItem(models.Model):'
    require(text.count(marker) == 1 and text.count(next_marker) == 1,
            'Reservation model anchors not found.')
    head, rest = text.split(marker, 1)
    body, tail = rest.split(next_marker, 1)
    body = replace_one(body,
        '    created = models.DateTimeField(auto_now_add=True)\n',
        '    guest_request = models.BooleanField(\n'
        '        default=False,\n'
        '        help_text="Public request awaiting manual hut approval; not a short payment hold.",\n'
        '    )\n\n'
        '    created = models.DateTimeField(auto_now_add=True)\n',
        'Reservation model')
    return head + marker + body + next_marker + tail


def patch_services(text):
    text = replace_one(text,
        '            status=Reservation.Status.PENDING,\n            created__lt=cutoff,\n',
        '            status=Reservation.Status.PENDING,\n            guest_request=False,\n            created__lt=cutoff,\n',
        'pending expiry candidate query')
    return replace_one(text,
        '                    status=Reservation.Status.PENDING,\n                    created__lt=cutoff,\n',
        '                    status=Reservation.Status.PENDING,\n                    guest_request=False,\n                    created__lt=cutoff,\n',
        'pending expiry locked query')


def patch_views(text):
    text = replace_one(text,
        'from django.contrib.admin.views.decorators import staff_member_required\n',
        'from django.contrib.admin.views.decorators import staff_member_required\n'
        'from django.contrib.auth.decorators import login_required\n',
        'login_required import')
    text = replace_one(text,
        '                    beds_by_room=booking.beds_by_room(),\n                    **guest,\n',
        '                    beds_by_room=booking.beds_by_room(),\n'
        '                    status=Reservation.Status.PENDING,\n'
        '                    guest_request=True,\n'
        '                    **guest,\n',
        'public booking creation')
    text = replace_one(text,
        '            else:\n                send_confirmation(request, reservation)\n                return redirect(reservation)\n',
        '            else:\n'
        '                from .guest_requests_v126 import send_guest_request_received\n'
        '                send_guest_request_received(request, reservation)\n'
        '                return redirect(reservation)\n',
        'public booking email')
    text = replace_one(text,
        '    if not user.is_staff:\n        raise PermissionDenied("Staff access required.")\n',
        '    if not user.is_authenticated:\n        raise PermissionDenied("Manager login required.")\n',
        'manager authorization (membership remains mandatory)')
    text = replace_one(text,
        '@staff_member_required\ndef manager_reservations(request):\n',
        '@login_required\ndef manager_reservations(request):\n',
        'manager reservations login')
    text = replace_one(text,
        '@staff_member_required\n@require_POST\ndef manager_reservation_action(request, code):\n',
        '@login_required\n@require_POST\ndef manager_reservation_action(request, code):\n',
        'manager action login')
    text = replace_one(text,
        '                reservation.status = Reservation.Status.CONFIRMED\n'
        '                reservation.save(update_fields=["status"])\n'
        '                messages.success(request, "Reservation confirmed.")\n',
        '                reservation.status = Reservation.Status.CONFIRMED\n'
        '                reservation.save(update_fields=["status"])\n'
        '                if reservation.guest_request:\n'
        '                    transaction.on_commit(\n'
        '                        lambda reservation=reservation: send_confirmation(request, reservation)\n'
        '                    )\n'
        '                messages.success(request, "Reservation confirmed.")\n',
        'manager approval notification')
    text = replace_one(text,
        '                reservation.status = Reservation.Status.CANCELLED\n'
        '                reservation.save(update_fields=["status"])\n'
        '                messages.success(request, "Reservation cancelled; beds are available again.")\n',
        '                reservation.status = Reservation.Status.CANCELLED\n'
        '                reservation.save(update_fields=["status"])\n'
        '                if reservation.guest_request:\n'
        '                    from .guest_requests_v126 import send_guest_request_declined\n'
        '                    transaction.on_commit(\n'
        '                        lambda reservation=reservation: send_guest_request_declined(request, reservation)\n'
        '                    )\n'
        '                messages.success(request, "Reservation cancelled; beds are available again.")\n',
        'manager decline notification')
    return text


def patch_public_template(text):
    text = replace_one(text,
        'We\'ll use these details for your reservation and confirmation.',
        'We\'ll send your request to the hut manager. Your stay is not confirmed until they approve it.',
        'public guest explanation')
    text = replace_one(text,
        'Confirm reservation <span aria-hidden="true">→</span>',
        'Request reservation <span aria-hidden="true">→</span>',
        'public submit button')
    text = replace_one(text,
        'Your reservation is checked again when you submit to prevent overbooking. A private booking link will be sent to your email.',
        'We check availability again before accepting your request. Selected beds are held while the hut reviews it. You will receive an email when the manager approves or declines.',
        'public submit note')
    text = replace_one(text,
        'Clear pricing, no account needed',
        'Manager approval required · no account needed',
        'public sidebar footnote')
    return text


def patch_reservation_template(text):
    text = replace_one(text,
        '<span class="ar-state ar-state-pending">Awaiting confirmation</span>',
        '<span class="ar-state ar-state-pending">{% if reservation.guest_request %}Awaiting hut approval{% else %}Awaiting confirmation{% endif %}</span>',
        'guest pending badge')
    text = replace_one(text,
        'Your beds are on hold, but your reservation is not yet confirmed. Keep this private link for updates.',
        '{% if reservation.guest_request %}Your request has been sent to the hut manager. Beds are held, but your stay is not confirmed until approved. We will email you after review.{% else %}Your beds are on hold, but your reservation is not yet confirmed. Keep this private link for updates.{% endif %}',
        'guest pending explanation')
    text = replace_one(text,
        '<p class="ar-status-note pending">Your beds are on hold. Your reservation is not yet confirmed.</p>',
        '<p class="ar-status-note pending">{% if reservation.guest_request %}Request received. Waiting for the hut manager to approve or decline it. Your selected beds are held until then.{% else %}Your beds are on hold. Your reservation is not yet confirmed.{% endif %}</p>',
        'guest pending summary')
    text = replace_one(text,
        '<div><dt>Status</dt><dd>{{ reservation.get_status_display }}</dd></div>',
        '<div><dt>Status</dt><dd>{% if reservation.guest_request and reservation.status == "pending" %}Awaiting approval{% else %}{{ reservation.get_status_display }}{% endif %}</dd></div>',
        'guest status')
    text = replace_one(text,
        '<h2 id="ar-beds-heading">Reserved beds</h2>',
        '<h2 id="ar-beds-heading">{% if reservation.guest_request and reservation.status == "pending" %}Beds requested{% else %}Reserved beds{% endif %}</h2>',
        'guest beds heading')
    return text


def patch_manager_template(text):
    text = replace_one(text,
        '{{ reservation.get_status_display }}</span></td>',
        '{% if reservation.guest_request and reservation.status == "pending" %}Awaiting approval{% else %}{{ reservation.get_status_display }}{% endif %}</span></td>',
        'manager pending badge')
    text = replace_one(text,
        '<button class="mr-confirm" type="submit">Confirm</button>',
        '<button class="mr-confirm" type="submit">{% if reservation.guest_request %}Approve{% else %}Confirm{% endif %}</button>',
        'manager approve button')
    text = replace_one(text,
        '<button class="mr-cancel" type="submit">Cancel</button>',
        '<button class="mr-cancel" type="submit">{% if reservation.guest_request and reservation.status == "pending" %}Decline{% else %}Cancel{% endif %}</button>',
        'manager decline button')
    return text


def patch_lifecycle(text):
    text = replace_one(text,
        '    qs = manageable_reservations(request.user).filter(status__in=Reservation.HOLDING)\n',
        '    qs = manageable_reservations(request.user).filter(status__in=Reservation.HOLDING).exclude(\n'
        '        status=Reservation.Status.PENDING, guest_request=True\n'
        '    )\n',
        'deposit lifecycle dashboard')
    return replace_one(text,
        '    candidates = Reservation.objects.filter(status__in=Reservation.HOLDING).values_list("pk", flat=True)\n',
        '    candidates = Reservation.objects.filter(status__in=Reservation.HOLDING).exclude(\n'
        '        status=Reservation.Status.PENDING, guest_request=True\n'
        '    ).values_list("pk", flat=True)\n',
        'deposit lifecycle automatic processing')


def patch_staff_reservation(text):
    text = replace_one(text,
        '                else:\n'
        '                    locked.status = target\n'
        '                    locked.save(update_fields=["status"])\n'
        '            if not error_message:\n',
        '                else:\n'
        '                    previous_status = locked.status\n'
        '                    locked.status = target\n'
        '                    locked.save(update_fields=["status"])\n'
        '                    if locked.guest_request and previous_status != target:\n'
        '                        if target == "confirmed":\n'
        '                            from bookings.views import send_confirmation\n'
        '                            transaction.on_commit(\n'
        '                                lambda locked=locked: send_confirmation(request, locked)\n'
        '                            )\n'
        '                        elif target == "cancelled":\n'
        '                            from bookings.guest_requests_v126 import send_guest_request_declined\n'
        '                            transaction.on_commit(\n'
        '                                lambda locked=locked: send_guest_request_declined(request, locked)\n'
        '                            )\n'
        '            if not error_message:\n',
        'hut staff reservation approval')
    return text


def patch_tests(text):
    return replace_one(text,
        '        self.assertContains(self.client.get(reservation.get_absolute_url()), "Confirmed")\n',
        '        self.assertEqual(reservation.status, Reservation.Status.PENDING)\n'
        '        self.assertTrue(reservation.guest_request)\n'
        '        self.assertContains(self.client.get(reservation.get_absolute_url()), "Awaiting hut approval")\n',
        'existing public booking test')


def patch_hut_tests(text):
    return replace_one(text,
        '        self.assertContains(response, "Confirm reservation")\n',
        '        self.assertContains(response, "Request reservation")\n',
        'v125 public hut test')

PATCHED = {
    'bookings/models.py': patch_models,
    'bookings/services.py': patch_services,
    'bookings/lifecycle.py': patch_lifecycle,
    'floorplans/staff_reservation.py': patch_staff_reservation,
    'bookings/views.py': patch_views,
    'bookings/templates/bookings/public_hut_v125.html': patch_public_template,
    'bookings/templates/bookings/reservation.html': patch_reservation_template,
    'bookings/templates/bookings/manager_reservations.html': patch_manager_template,
    'bookings/tests.py': patch_tests,
    'bookings/test_public_hut_v125.py': patch_hut_tests,
}


def safe_target(rel):
    path = Path(rel)
    require(not path.is_absolute() and '..' not in path.parts, f'Unsafe target: {rel}')
    target = ROOT / path
    require(not target.is_symlink(), f'Refusing symlink: {rel}')
    for parent in list(target.parents)[:-1]:
        if parent == ROOT:
            break
        require(not parent.is_symlink(), f'Refusing symlink directory: {parent}')
    require(ROOT in target.parents, f'Outside project: {rel}')
    return target


def atomic_write(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.sd126_', dir=target.parent, delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (target.stat().st_mode & 0o777) if target.exists() else 0o644)
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from the SummitDesk project root.')
    require((ROOT / 'bookings/templates/bookings/public_base_v124.html').is_file(), 'Install v124 first.')
    require((ROOT / 'bookings/templates/bookings/public_hut_v125.html').is_file(), 'Install v125 first.')
    require((ROOT / 'bookings/migrations/0012_guestaccesslink_guestchangerequest.py').is_file(), 'Missing bookings migration 0012.')

    payload = {}
    for rel, fn in PATCHED.items():
        path = safe_target(rel)
        require(path.is_file(), f'Missing required source: {rel}')
        source = path.read_text(encoding='utf-8')
        updated = fn(source)
        require(updated != source, f'No change generated for {rel}')
        payload[rel] = updated.encode('utf-8')
    for rel, filename in NEW_FILES.items():
        path = safe_target(rel)
        require(not path.exists(), f'Already installed or conflicting file: {rel}')
        src = PACKAGE / filename
        require(src.is_file() and not src.is_symlink(), f'Missing package file: {filename}')
        payload[rel] = src.read_bytes()

    for rel, data in payload.items():
        if rel.endswith('.py'):
            compile(data, rel, 'exec')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'guest_approval_{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel, data in payload.items():
        target = safe_target(rel)
        exists = target.is_file()
        manifest.append({'path': rel, 'existed': exists, 'installed_sha256': hashlib.sha256(data).hexdigest()})
        if exists:
            original = backup / rel
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, original)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    try:
        for rel, data in payload.items():
            atomic_write(safe_target(rel), data)
    except Exception:
        for entry in manifest:
            dest = safe_target(entry['path'])
            if entry['existed']:
                shutil.copy2(backup / entry['path'], dest)
            else:
                dest.unlink(missing_ok=True)
        raise

    print('Guest request approval workflow installed (files only).')
    print('Backup:', backup)
    print('NEXT: Run python manage.py check and python manage.py migrate bookings')
    print('The migration is REQUIRED before serving requests.')


if __name__ == '__main__':
    main()
