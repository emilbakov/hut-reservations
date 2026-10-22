#!/usr/bin/env python3
"""Install SummitDesk v128 request operations on an existing v127 project.

Preflight checks all patches and Python syntax before changing any files.
Each existing file is backed up, and writes are atomic. No schema/data changes.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent

NEW = {
    'bookings/request_operations_v128.py': 'request_operations_v128.py',
    'bookings/test_request_operations_v128.py': 'test_request_operations_v128.py',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def replace_once(source, old, new, label):
    count = source.count(old)
    require(count == 1, f'Unexpected {label}: expected 1 match, found {count}. No files changed.')
    return source.replace(old, new, 1)


def patch_urls(source):
    source = replace_once(
        source,
        'from . import approval_dashboard_v127\n',
        'from . import approval_dashboard_v127\nfrom .request_operations_v128 import request_export\n',
        'v127 URL imports',
    )
    return replace_once(
        source,
        '    # Guest requests approval dashboard\n',
        '    # Guest request CSV export (same manager scope as dashboard)\n'
        '    path("staff/reservations/requests/export/", request_export, name="request_export"),\n\n'
        '    # Guest requests approval dashboard\n',
        'v127 dashboard route',
    )


def patch_view(source):
    source = replace_once(source,
        'from django.db.models import Q\n',
        'from datetime import timedelta\n\nfrom django.utils import timezone\n',
        'v127 view imports',
    )
    source = replace_once(source,
        'from .views import manageable_reservations, permitted_hut_selection\n',
        'from .request_operations_v128 import (\n'
        '    filter_requests, get_request_filters, pending_priorities, scoped_public_requests,\n'
        ')\n',
        'v127 manager authorization imports',
    )
    start = source.index('    huts, selected_hut, selected_slug = permitted_hut_selection(request)\n')
    end = source.index('    page = Paginator(\n', start)
    old = source[start:end]
    new = '''    huts, selected_hut, selected_slug, scoped = scoped_public_requests(request)
    now = timezone.now()
    today = timezone.localdate()
    filters = get_request_filters(request)
    status, query, priority = filters['status'], filters['q'], filters['priority']

    counts = {
        'pending': scoped.filter(status=Reservation.Status.PENDING).count(),
        'confirmed': scoped.filter(status=Reservation.Status.CONFIRMED).count(),
        'cancelled': scoped.filter(status=Reservation.Status.CANCELLED).count(),
    }
    priority_counts = pending_priorities(scoped, now=now, today=today)
    results = filter_requests(scoped, filters, now=now, today=today)

'''
    source = replace_once(source, old, new, 'v127 queue filter logic')
    source = replace_once(source,
        '        reservation.reviewable_here = (\n',
        '        reservation.waiting_over_24h = (\n'
        '            reservation.status == Reservation.Status.PENDING\n'
        '            and reservation.created <= now - timedelta(hours=24)\n'
        '        )\n'
        '        reservation.arrival_due = (\n'
        '            reservation.status == Reservation.Status.PENDING\n'
        '            and reservation.check_in <= today + timedelta(days=2)\n'
        '        )\n'
        '        reservation.reviewable_here = (\n',
        'priority indicators',
    )
    return replace_once(source,
        "        'counts': counts, 'status_filter': status, 'q': query,\n",
        "        'counts': counts, 'status_filter': status, 'q': query,\n"
        "        'priority_counts': priority_counts, 'priority_filter': priority,\n",
        'priority template context',
    )


def patch_template(source):
    source = replace_once(source,
        'grid-template-columns:minmax(170px,1fr) minmax(180px,2fr) auto;',
        'grid-template-columns:minmax(170px,1fr) minmax(180px,2fr) minmax(170px,1fr) auto;',
        'priority filter layout',
    )
    source = replace_once(source,
        '  @media(max-width:1050px)',
        '  .aq-priority-summary{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 20px}'
        '.aq-priority-summary a{background:#fff;border:1px solid var(--line);border-radius:13px;padding:13px 17px;text-decoration:none;display:flex;align-items:center;gap:10px;min-height:48px;font-size:.84rem;font-weight:750}'
        '.aq-priority-summary strong{font-size:1.18rem;color:#9b5d0b}'
        '.aq-alerts{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}'
        '.aq-alert{font-size:.7rem;font-weight:800;background:#fff1d6;color:#88520c;padding:5px 8px;border-radius:7px}'
        '.aq-alert-due{background:#fbe1df;color:#973e39}'
        '.aq-download{display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;min-height:42px;border:1px solid #aecab5;border-radius:10px;background:#f6faf6;text-decoration:none!important;font-size:.83rem;font-weight:800;color:var(--pine)!important}'
        '.aq-heading-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}'
        '  @media(max-width:1050px)',
        'v128 dashboard styling',
    )
    source = replace_once(source,
        '  </nav>\n\n  <section class="aq-panel"',
        '''  </nav>

  <section class="aq-priority-summary" aria-label="Pending request priorities">
    <a href="?status=pending&amp;priority=waiting24{% if selected_slug %}&amp;hut={{ selected_slug|urlencode }}{% endif %}"><strong>{{ priority_counts.waiting24 }}</strong> Waiting over 24 hours ↗</a>
    <a href="?status=pending&amp;priority=arrival48{% if selected_slug %}&amp;hut={{ selected_slug|urlencode }}{% endif %}"><strong>{{ priority_counts.arrival48 }}</strong> Arrival due within 2 days or overdue ↗</a>
  </section>

  <section class="aq-panel"''',
        'priority summary',
    )
    source = replace_once(source,
        '      <button type="submit" class="aq-btn aq-btn-dark">Apply filters →</button>',
        '''      <div class="aq-field"><label for="aq-priority">Review priority</label><select name="priority" id="aq-priority">
        <option value="all" {% if priority_filter == 'all' %}selected{% endif %}>All priorities</option>
        <option value="waiting24" {% if priority_filter == 'waiting24' %}selected{% endif %}>Waiting over 24 hours</option>
        <option value="arrival48" {% if priority_filter == 'arrival48' %}selected{% endif %}>Arrival due / overdue</option>
      </select></div>
      <button type="submit" class="aq-btn aq-btn-dark">Apply filters →</button>''',
        'priority selector',
    )
    source = replace_once(source,
        '<p>{{ page.paginator.count }} matching request{{ page.paginator.count|pluralize }}</p></div>',
        '''<div class="aq-heading-actions"><p>{{ page.paginator.count }} matching request{{ page.paginator.count|pluralize }}</p><a class="aq-download" href="{% url 'bookings:request_export' %}?status={{ status_filter|urlencode }}&amp;hut={{ selected_slug|urlencode }}&amp;q={{ q|urlencode }}&amp;priority={{ priority_filter|urlencode }}">↓ Download CSV (all matches)</a></div></div>''',
        'CSV download link',
    )
    source = replace_once(source,
        '<small>Requested {{ reservation.created|date:"j M Y, H:i" }}</small></div><span class="aq-pill',
        '''<small>Requested {{ reservation.created|date:"j M Y, H:i" }}</small>{% if reservation.waiting_over_24h or reservation.arrival_due %}<div class="aq-alerts">{% if reservation.waiting_over_24h %}<span class="aq-alert">Waiting over 24 hours</span>{% endif %}{% if reservation.arrival_due %}<span class="aq-alert aq-alert-due">Arrival due</span>{% endif %}</div>{% endif %}</div><span class="aq-pill''',
        'per-card priority indicators',
    )
    source = replace_once(source,
        "{% if status_filter == 'pending' and not q %}",
        "{% if status_filter == 'pending' and not q and priority_filter == 'all' %}",
        'empty priority state',
    )
    pagination_token = '&amp;q={{ q|urlencode }}&amp;page='
    require(source.count(pagination_token) == 2,
            'Unexpected v127 pagination layout; no files changed.')
    source = source.replace(
        pagination_token,
        '&amp;q={{ q|urlencode }}&amp;priority={{ priority_filter|urlencode }}&amp;page=',
    )
    return source


PATCH = {
    'bookings/urls.py': patch_urls,
    'bookings/approval_dashboard_v127.py': patch_view,
    'bookings/templates/bookings/approval_dashboard_v127.html': patch_template,
}


def target_path(rel):
    relpath = Path(rel)
    require(not relpath.is_absolute() and '..' not in relpath.parts, f'Unsafe path: {rel}')
    target = ROOT / relpath
    require(ROOT in target.parents, f'Path outside project: {rel}')
    require(not target.is_symlink(), f'Refusing symlink: {rel}')
    parent = target.parent
    while parent != ROOT:
        require(not parent.is_symlink(), f'Refusing symlink directory: {parent}')
        parent = parent.parent
    return target


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.sd128_', delete=False) as fh:
            temp = Path(fh.name)
            fh.write(data)
        os.chmod(temp, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / 'manage.py').is_file(), 'Run from the SummitDesk project root.')
    require((ROOT / 'bookings/approval_dashboard_v127.py').is_file(), 'Install v127 first.')
    require((ROOT / 'bookings/migrations/0013_reservation_guest_request.py').is_file(), 'v126 guest requests schema is missing.')
    payload = {}
    for rel, transform in PATCH.items():
        target = target_path(rel)
        require(target.is_file(), f'Missing required source: {rel}')
        original = target.read_text(encoding='utf-8')
        updated = transform(original)
        require(updated != original, f'No change generated for {rel}')
        payload[rel] = updated.encode('utf-8')
    for rel, srcname in NEW.items():
        target = target_path(rel)
        require(not target.exists(), f'Already installed or conflicting file: {rel}')
        src = PKG / srcname
        require(src.is_file() and not src.is_symlink(), f'Missing payload: {srcname}')
        payload[rel] = src.read_bytes()
    for rel, data in payload.items():
        if rel.endswith('.py'):
            compile(data, rel, 'exec')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = ROOT / 'summitdesk_backups' / f'request_operations_{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    manifest = []
    for rel, data in payload.items():
        target = target_path(rel)
        existed = target.is_file()
        manifest.append({
            'path': rel, 'existed': existed,
            'installed_sha256': hashlib.sha256(data).hexdigest(),
        })
        if existed:
            destination = backup / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
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
    print('SummitDesk v128 installed: request priorities and scoped CSV export.')
    print('Backup:', backup)
    print('No database migrations needed. Run Django checks and tests before restarting.')


if __name__ == '__main__':
    main()
