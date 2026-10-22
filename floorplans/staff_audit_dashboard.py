"""V33: manager-only, hut-scoped reservation event explorer and CSV export."""
import csv
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from .staff_tasks import access
from .reservation_history import ReservationHistoryEvent

MAX_EXPORT_ROWS = 10000

def _csv_safe(value):
    """Prevent spreadsheet formula execution, including after leading whitespace."""
    text = '' if value is None else str(value)
    if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + text
    return text

@login_required
@require_GET
def staff_audit_dashboard(request, hut_id):
    hut, manager, _ = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden('Only hut managers may view audit events.')
    base = ReservationHistoryEvent.objects.filter(hut=hut)
    kinds = list(base.order_by().values_list('kind', flat=True).distinct())
    actors = list(base.filter(actor__isnull=False).order_by('actor__username')
                  .values('actor_id', 'actor__username').distinct())
    kind = request.GET.get('kind', '').strip()
    actor = request.GET.get('actor', '').strip()
    start = request.GET.get('from', '').strip()
    end = request.GET.get('to', '').strip()
    code = request.GET.get('code', '').strip()[:32]
    if kind and kind not in kinds:
        return HttpResponseBadRequest('Invalid event type')
    if actor and (not actor.isdecimal() or not any(str(a['actor_id']) == actor for a in actors)):
        return HttpResponseBadRequest('Invalid staff filter')
    try:
        from_day = date.fromisoformat(start) if start else None
        to_day = date.fromisoformat(end) if end else None
    except ValueError:
        return HttpResponseBadRequest('Dates must be YYYY-MM-DD')
    if from_day and to_day and from_day > to_day:
        return HttpResponseBadRequest('Start date must precede end date')
    if from_day and to_day and (to_day - from_day).days > 3660:
        return HttpResponseBadRequest('Date range is too large')
    qs = base
    if kind:
        qs = qs.filter(kind=kind)
    if actor:
        qs = qs.filter(actor_id=int(actor))
    if from_day:
        qs = qs.filter(created_at__date__gte=from_day)
    if to_day:
        qs = qs.filter(created_at__date__lte=to_day)
    if code:
        qs = qs.filter(reservation_code__icontains=code)
    total = qs.count()
    by_kind = list(qs.order_by().values('kind').annotate(count=Count('pk')).order_by('-count', 'kind')[:30])
    by_actor = list(qs.order_by().values('actor_id', 'actor__username').annotate(count=Count('pk')).order_by('-count', 'actor__username')[:30])
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="summitdesk_audit_hut_{hut.pk}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Timestamp (UTC)', 'Reservation code', 'Event type', 'Description', 'Staff username', 'Field changes (JSON)'])
        import json
        for event in qs.select_related('actor').order_by('-created_at', '-pk')[:MAX_EXPORT_ROWS].iterator(chunk_size=500):
            writer.writerow([_csv_safe(event.created_at.isoformat()), _csv_safe(event.reservation_code),
                             _csv_safe(event.kind), _csv_safe(event.description),
                             _csv_safe(event.actor.get_username() if event.actor else ''),
                             _csv_safe(json.dumps(event.changes or {}, ensure_ascii=False))])
        return response
    page = Paginator(qs.select_related('actor').order_by('-created_at', '-pk'), 50).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    query.pop('export', None)
    return render(request, 'floorplans/staff_audit_dashboard.html', {
        'hut': hut, 'events': page, 'total': total, 'by_kind': by_kind, 'by_actor': by_actor,
        'kinds': sorted(kinds), 'actors': actors, 'selected_kind': kind,
        'selected_actor': actor, 'start': start, 'end': end, 'code': code,
        'filter_query': query.urlencode(), 'export_limit': MAX_EXPORT_ROWS,
    })
