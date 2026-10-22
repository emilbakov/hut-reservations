"""Manager-only read-only reminder send history and CSV export (v132).

The history records SMTP submissions, not guaranteed inbox delivery. Only
records belonging to the signed-in user can be viewed or exported.
"""
import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .models import Hut, ManagerRequestDigestLog

PERIODS = (
    ('7', 'Last 7 days'),
    ('30', 'Last 30 days'),
    ('90', 'Last 90 days'),
    ('365', 'Last 365 days'),
    ('all', 'All recorded history'),
)
ALLOWED_PERIODS = {value for value, _label in PERIODS}


def _safe_csv_cell(value):
    """Prevent spreadsheet formula execution in user-controlled text cells."""
    value = str(value or '')
    if value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


@login_required
@require_GET
@never_cache
def manager_digest_history(request):
    manager = request.user
    assigned = Hut.objects.filter(is_active=True, managers=manager).exists()
    if not (manager.is_active and (assigned or manager.is_superuser)):
        raise PermissionDenied('Only active hut managers can view reminder history.')

    period = request.GET.get('days', '30')
    if period not in ALLOWED_PERIODS:
        return HttpResponseBadRequest('Invalid history period.')
    output_format = request.GET.get('format', 'html')
    if output_format not in ('html', 'csv'):
        return HttpResponseBadRequest('Invalid history format.')

    logs = ManagerRequestDigestLog.objects.filter(manager=manager)
    if period != 'all':
        first_day = timezone.localdate() - timedelta(days=int(period) - 1)
        logs = logs.filter(digest_date__gte=first_day)
    logs = logs.order_by('-digest_date', '-sent_at', '-pk')

    if output_format == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="summitdesk-reminder-history-{period}.csv"'
        )
        response.write('\ufeff')  # Excel-compatible UTF-8.
        writer = csv.writer(response)
        writer.writerow(['Date', 'Recorded at (local)', 'Recipient', 'Huts', 'Requests'])
        for entry in logs.iterator(chunk_size=200):
            writer.writerow([
                entry.digest_date.isoformat(),
                timezone.localtime(entry.sent_at).isoformat(timespec='seconds'),
                _safe_csv_cell(entry.recipient),
                entry.hut_count,
                entry.request_count,
            ])
        return response

    totals = logs.aggregate(huts=Sum('hut_count'), requests=Sum('request_count'))
    page = Paginator(logs, 20).get_page(request.GET.get('page'))
    return render(request, 'bookings/manager_digest_history_v132.html', {
        'period': period,
        'periods': PERIODS,
        'page': page,
        'record_count': page.paginator.count,
        'total_huts': totals['huts'] or 0,
        'total_requests': totals['requests'] or 0,
    })
