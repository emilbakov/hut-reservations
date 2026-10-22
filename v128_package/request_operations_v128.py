"""Read-only queue prioritization and secure CSV export for guest requests.

Authorization and hut selection intentionally reuse the existing v127/v126
manager scope. Export and dashboard share one filter implementation.
"""
import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Reservation
from .views import manageable_reservations, permitted_hut_selection


PRIORITIES = {'all', 'waiting24', 'arrival48'}
STATUSES = {'all', 'pending', 'confirmed', 'cancelled'}


def scoped_public_requests(request):
    """Return only requests the current user can see, for the selected hut."""
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    scoped = manageable_reservations(request.user).filter(guest_request=True)
    if selected_hut is not None:
        scoped = scoped.filter(items__room__hut=selected_hut)
    return huts, selected_hut, selected_slug, scoped.distinct()


def get_request_filters(request):
    status = request.GET.get('status', 'pending').strip()
    if status not in STATUSES:
        status = 'pending'
    query = request.GET.get('q', '').strip()[:120]
    priority = request.GET.get('priority', 'all').strip()
    if priority not in PRIORITIES or status not in {'pending', 'all'}:
        priority = 'all'
    return {'status': status, 'q': query, 'priority': priority}


def filter_requests(scoped, filters, *, now=None, today=None):
    """Apply exactly the same filters/order for the UI and CSV download."""
    now = now or timezone.now()
    today = today or timezone.localdate()
    results = scoped
    status = filters['status']
    if status != 'all':
        results = results.filter(status=status)
    if filters['q']:
        query = filters['q']
        results = results.filter(
            Q(name__icontains=query) | Q(email__icontains=query)
            | Q(code__icontains=query) | Q(phone__icontains=query)
        )
    if filters['priority'] == 'waiting24':
        results = results.filter(
            status=Reservation.Status.PENDING,
            created__lte=now - timedelta(hours=24),
        )
    elif filters['priority'] == 'arrival48':
        # Includes already-overdue arrivals, which also need prompt attention.
        results = results.filter(
            status=Reservation.Status.PENDING,
            check_in__lte=today + timedelta(days=2),
        )
    if status == 'pending' or filters['priority'] != 'all':
        return results.order_by('created', 'pk')
    return results.order_by('-created', '-pk')


def pending_priorities(scoped, *, now=None, today=None):
    now = now or timezone.now()
    today = today or timezone.localdate()
    pending = scoped.filter(status=Reservation.Status.PENDING)
    return {
        'waiting24': pending.filter(created__lte=now - timedelta(hours=24)).count(),
        'arrival48': pending.filter(check_in__lte=today + timedelta(days=2)).count(),
    }


def safe_csv_cell(value):
    """Prevent spreadsheet formula execution from untrusted guest/hut fields."""
    if value is None:
        return ''
    text = str(value).replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
    leading = text.lstrip(' \t\ufeff\u200b')
    if leading.startswith(('=', '+', '-', '@')) or text.startswith('\t'):
        return "'" + text
    return text


class _CSVBuffer:
    def write(self, value):
        return value


def _export_rows(queryset, now):
    writer = csv.writer(_CSVBuffer())
    yield '\ufeff' + writer.writerow([
        'Reference', 'Status', 'Requested at', 'Waiting hours',
        'Guest name', 'Email', 'Phone', 'Hut', 'Rooms',
        'Check-in', 'Check-out', 'Nights', 'Beds',
        'Estimated total (EUR)', 'Guest notes',
    ])
    # Chunked iteration keeps a large export from loading every reservation
    # into memory; prefetch still works with Django iterator(chunk_size=...).
    for reservation in queryset.prefetch_related('items__room__hut').iterator(chunk_size=200):
        items = list(reservation.items.all())
        hut_names = sorted({
            item.room.hut.name for item in items if item.room.hut_id
        })
        rooms = '; '.join(
            f'{item.room.name} ({item.beds} beds)' for item in items
        )
        waiting_hours = (
            max(0, int((now - reservation.created).total_seconds() // 3600))
            if reservation.status == Reservation.Status.PENDING else ''
        )
        row = [
            reservation.code, reservation.status,
            timezone.localtime(reservation.created).isoformat(timespec='seconds'),
            waiting_hours, reservation.name, reservation.email, reservation.phone,
            '; '.join(hut_names), rooms,
            reservation.check_in.isoformat(), reservation.check_out.isoformat(),
            reservation.nights, sum(item.beds for item in items),
            f'{sum((item.subtotal for item in items), 0):.2f}',
            reservation.notes,
        ]
        yield writer.writerow([safe_csv_cell(cell) for cell in row])


@login_required
@require_GET
def request_export(request):
    """Download only the filtered requests visible to this hut manager."""
    _, _, _, scoped = scoped_public_requests(request)
    now = timezone.now()
    today = timezone.localdate()
    filters = get_request_filters(request)
    results = filter_requests(scoped, filters, now=now, today=today)
    response = StreamingHttpResponse(
        _export_rows(results, now), content_type='text/csv; charset=utf-8'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="summitdesk_guest_requests_{today:%Y%m%d}.csv"'
    )
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
