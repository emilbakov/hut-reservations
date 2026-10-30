"""Read-only deposit work queue. Lifecycle writes stay in the existing services."""
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import HutDepositPolicy, ReservationNotification

FILTERS = (
    ('attention', 'Needs attention'), ('awaiting', 'Awaiting deposit'),
    ('soon', 'Due within 24 hours'), ('overdue', 'Overdue'), ('partial', 'Partial payments'),
    ('review', 'Needs review'), ('received', 'Deposit met'), ('closed', 'Closed'), ('legacy', 'Legacy policy'),
    ('all', 'All records'),
)


def classify(reservation, policies, now):
    items = list(reservation.items.all())
    hut_ids = {i.room.hut_id for i in items}
    if len(hut_ids) != 1 or None in hut_ids:
        return None
    hut_id = next(iter(hut_ids))
    hold = reservation.deposit_request
    ledger = list(reservation.payment_transactions.all())
    net = sum(((-p.amount if p.kind == 'refund' else p.amount) for p in ledger), Decimal('0.00'))
    unreviewed = reservation.guest_request and reservation.status == 'pending' and (not hold or hold.state == 'withdrawn')
    if unreviewed and net == 0:
        return None  # No approved terms exist; do not invent a payment obligation.
    legacy = hold is None and not unreviewed
    policy = policies.get(hut_id)
    target = hold.amount if hold and hold.state != 'withdrawn' else None
    due = hold.due_at if target is not None else None
    if legacy:
        percentage = policy.percentage if policy else 30
        target = (Decimal(reservation.total_price)*Decimal(percentage)/100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        date = timezone.localdate(reservation.created) + timedelta(days=policy.due_days if policy else 3)
        due = timezone.make_aware(datetime.combine(date, time.max))
    remaining = max(target-net, Decimal('0.00')) if target is not None else None
    stay = getattr(reservation, 'guest_stay', None)
    in_house = bool(stay and stay.checked_in_at and not stay.checked_out_at)
    processing_expiry = bool(hold and hold.state == 'awaiting' and due <= now and not in_house)
    expired = bool(hold and hold.state == 'expired') or processing_expiry
    closed = reservation.status == 'cancelled' or expired
    settlement = getattr(reservation, 'cancellation_settlement', None)
    settled = bool(settlement and net == settlement.retained_at_cancellation and
                   not any(p.created > settlement.created for p in ledger))
    review = (in_house and hold is not None and hold.state == 'awaiting' and due <= now) or net < 0 or bool(hold and hold.state == 'review') or (closed and net > 0 and not settled) or (unreviewed and net != 0)
    if hold and hold.state == 'paid' and reservation.status == 'confirmed' and remaining > 0:
        review = True
    awaiting = not closed and not review and remaining is not None and remaining > 0
    overdue = processing_expiry or (awaiting and due is not None and due <= now)
    soon = awaiting and due is not None and now < due <= now+timedelta(hours=24)
    partial = awaiting and net > 0
    received = not closed and not review and target is not None and remaining == 0
    flags = {'attention': awaiting or review or processing_expiry, 'awaiting': awaiting, 'soon': soon,
             'overdue': overdue, 'partial': partial, 'review': review, 'received': received,
             'closed': closed and not review and not processing_expiry, 'legacy': legacy, 'all': True}
    if review:
        label = _('Needs review')
        reason = (_('Checked in; overdue hold needs review') if in_house and due and due <= now else
                  _('Expired or cancelled with recorded funds') if closed else
                  _('Payment recorded before approval') if unreviewed else
                  _('Check payment balance') if net < 0 or (hold and hold.state == 'paid') else
                  _('Deposit received; room availability needs review'))
        tone = 'review'
    elif processing_expiry:
        label, tone = _('Deadline passed'), 'overdue'
        reason = _('Deadline passed; awaiting hold release. Do not request payment.')
    elif closed:
        label, tone = (_('Expired') if expired else _('Cancelled')), 'closed'
        reason = _('Funds settled') if settled and net else _('No deposit payment is requested')
    elif received:
        label, tone = (_('No deposit required') if target == 0 else _('Deposit met')), 'received'
        reason = _('Booking balance may still remain')
    else:
        label = _('Overdue') if overdue else _('Partial payment') if partial else _('Awaiting deposit')
        tone = 'overdue' if overdue else 'soon' if soon else 'awaiting'
        reason = _('Previous deposit policy; no automatic hold release') if legacy else _('Beds held until the approved deadline')
    reminder = None
    reminder_at = None
    if hold and hold.state == 'awaiting' and not expired:
        notices = getattr(reservation, 'deposit181_reminders', [])
        notice = notices[0] if notices else None
        if notice:
            reminder = {'sent': _('Reminder sent'), 'failed': _('Reminder delivery failed'),
                        'pending': _('Reminder queued'), 'skipped': _('Reminder skipped')}.get(notice.status)
            reminder_at = notice.sent_at
        elif not hold.reminders_enabled:
            reminder = _('Reminders disabled')
        else:
            reminder, reminder_at = _('Reminder scheduled'), hold.reminder_at
    history = reverse('bookings:reservation_payments', args=[reservation.code])
    return {'reservation': reservation, 'hut': items[0].room.hut, 'target': target, 'due_at': due,
            'net_paid': net, 'remaining': remaining, 'overdue': overdue, 'flags': flags,
            'label': label, 'reason': reason, 'tone': tone, 'legacy': legacy,
            'reminder': reminder, 'reminder_at': reminder_at,
            'can_record': awaiting and not expired, 'payments_url': history,
            'history_url': history+'#payment-history',
            'sort': (0 if review else 1 if overdue else 2 if soon else 3 if awaiting else 4,
                     due or reservation.created, -reservation.pk)}


def dashboard_context(request, qs, huts, selected_hut, selected_slug):
    now = timezone.now()
    query = request.GET.get('q', '').strip()[:120]
    selected = request.GET.get('state', 'attention')
    if selected not in dict(FILTERS):
        selected = 'attention'
    if selected_hut:
        qs = qs.filter(items__room__hut=selected_hut)
    if query:
        qs = qs.filter(Q(name__icontains=query)|Q(email__icontains=query)|Q(phone__icontains=query)|Q(code__icontains=query))
    qs = qs.distinct().select_related('deposit_request', 'cancellation_settlement', 'guest_stay').prefetch_related(
        'items__room__hut', 'payment_transactions', Prefetch('delivery_notifications',
            queryset=ReservationNotification.objects.filter(kind='deposit_reminder_guest').order_by('-pk'),
            to_attr='deposit181_reminders'))
    policies = {p.hut_id: p for p in HutDepositPolicy.objects.filter(hut__in=huts)}
    rows = [row for r in qs if (row := classify(r, policies, now)) is not None]
    counts = {key: sum(row['flags'][key] for row in rows) for key, label in FILTERS}
    visible = sorted((row for row in rows if row['flags'][selected]), key=lambda row: row['sort'])
    page = Paginator(visible, 25).get_page(request.GET.get('page'))
    base = {'hut': selected_slug, 'q': query}
    def url(state=selected, number=None):
        params = {**base, 'state': state}
        if number is not None:
            params['page'] = number
        return '?'+urlencode({k: v for k, v in params.items() if v != ''})
    navigation = [{'key': key, 'label': _(label), 'count': counts[key], 'url': url(key), 'current': key == selected}
                  for key, label in FILTERS]
    policy = policies.get(selected_hut.pk) if selected_hut else None
    return {'rows': page.object_list, 'page': page, 'counts': counts, 'navigation': navigation,
            'metrics': [x for x in navigation if x['key'] in ('awaiting', 'soon', 'partial', 'review')],
            'overdue_url': url('overdue'), 'state_filter': selected, 'state_label': _(dict(FILTERS)[selected]),
            'q': query, 'huts': huts, 'selected_hut': selected_hut, 'selected_slug': selected_slug,
            'manager_mode': not request.user.is_superuser, 'policy': policy,
            'currency': settings.BOOKING_CURRENCY, 'hut_timezone': settings.TIME_ZONE,
            'total_awaiting': counts['awaiting'], 'overdue_count': counts['overdue'],
            'previous_url': url(number=page.previous_page_number()) if page.has_previous() else None,
            'next_url': url(number=page.next_page_number()) if page.has_next() else None}
