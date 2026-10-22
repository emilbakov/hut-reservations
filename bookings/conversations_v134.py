"""v134 reservation-scoped guest/manager messaging and editable quick replies.

Guest messages are sent *inside SummitDesk* through a revocable guest token.
Manager messages are always visible in-app; email copies are optional.
Incoming SMTP email replies are not ingested.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .communications import validate_text
from .deposits import deposit_summary, single_hut_id
from .models import GuestConversationMessage, GuestMessageLog, Hut, HutQuickReply, Reservation
from .self_service import guest_reservation
from .views import manageable_reservations, permitted_hut_selection


BUILTIN_REPLIES = (
    ('Check-in instructions', 'Check-in details for {code}',
     'Hello {guest},\n\nWe look forward to welcoming you at {hut} on {check_in}. '
     'Please contact us if you need to arrange a different arrival time.\n'),
    ('Directions', 'Getting to {hut}',
     'Hello {guest},\n\nHere are the directions for your stay at {hut}.\n'
     '[Add directions and a meeting point before sending.]\n'),
    ('Parking', 'Parking information for {hut}',
     'Hello {guest},\n\nHere is the parking information for your visit to {hut}.\n'
     '[Add parking details before sending.]\n'),
    ('Special requests', 'Your request for reservation {code}',
     'Hello {guest},\n\nThank you for your message. '
     'Please tell us more about your special request so we can help.\n'),
)


def _hut_for_reservation(reservation):
    hut_id = single_hut_id(reservation)
    if not hut_id:
        raise Http404('Messaging requires a single-hut reservation.')
    return get_object_or_404(Hut, pk=hut_id)


def _authorized_reservation(user, code):
    reservation = get_object_or_404(manageable_reservations(user), code=code)
    return reservation, _hut_for_reservation(reservation)


def render_reply(subject, body, reservation, hut):
    """Render a small safe set of simple placeholders, never arbitrary attributes."""
    validate_text(subject)
    validate_text(body)
    summary = deposit_summary(reservation)
    values = {
        'guest': reservation.name, 'hut': hut.name, 'code': reservation.code,
        'check_in': str(reservation.check_in), 'check_out': str(reservation.check_out),
        'total': str(reservation.total_price),
        'currency': getattr(settings, 'BOOKING_CURRENCY', 'EUR'),
        'remaining': str(summary['remaining']) if summary else '0',
        'due_date': str(summary['due_date']) if summary else '',
    }
    rendered_subject = subject.format_map(values)
    rendered_body = body.format_map(values)
    if not rendered_subject.strip() or len(rendered_subject) > 200 or '\n' in rendered_subject or '\r' in rendered_subject:
        raise ValueError('Subject must be 1–200 characters and contain no line breaks.')
    if not rendered_body.strip() or len(rendered_body) > 4000:
        raise ValueError('Message must be 1–4000 characters.')
    return rendered_subject, rendered_body


def _presets(reservation, hut):
    replies = []
    for title, subject, body in BUILTIN_REPLIES:
        replies.append({'title': title + ' (built-in)', 'subject': subject, 'body': body})
    for item in HutQuickReply.objects.filter(hut=hut, enabled=True):
        replies.append({'title': item.title, 'subject': item.subject, 'body': item.body})
    prepared = []
    for item in replies:
        try:
            subject, body = render_reply(item['subject'], item['body'], reservation, hut)
        except ValueError:
            continue
        prepared.append({'title': item['title'], 'subject': subject, 'body': body})
    return prepared


@staff_member_required
@never_cache
@require_http_methods(['GET'])
def conversation_inbox(request):
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    qs = manageable_reservations(request.user)
    if selected_hut:
        qs = qs.filter(items__room__hut=selected_hut)
    query = request.GET.get('q', '').strip()[:120]
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(email__icontains=query))
    reservations = (qs.distinct()
        .annotate(last_message_at=Max('conversation_messages__created_at'))
        .annotate(last_activity=Coalesce('last_message_at', 'created'))
        .order_by('-last_activity')[:40])
    return render(request, 'bookings/conversation_inbox_v134.html', {
        'huts': huts, 'selected_hut': selected_hut, 'selected_slug': selected_slug,
        'q': query, 'reservations': reservations,
    })


@staff_member_required
@never_cache
@require_http_methods(['GET', 'POST'])
def conversation_thread(request, code):
    reservation, hut = _authorized_reservation(request.user, code)
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        try:
            if len(subject) > 200 or len(body) > 4000:
                raise ValueError('Subject or message is too long.')
            subject, body = render_reply(subject, body, reservation, hut)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('bookings:conversation_thread', code=code)

        send_email = request.POST.get('send_email') == 'on'
        if send_email and not reservation.email:
            messages.error(request, 'No guest email address. Uncheck email to send in-app only.')
            return redirect('bookings:conversation_thread', code=code)

        entry = GuestConversationMessage.objects.create(
            reservation=reservation, hut=hut,
            sender=GuestConversationMessage.Sender.MANAGER,
            sent_by=request.user, subject=subject, body=body,
            recipient=reservation.email if send_email else '',
            delivery=(GuestConversationMessage.Delivery.SENDING if send_email
                      else GuestConversationMessage.Delivery.IN_APP),
        )
        if send_email:
            try:
                email_subject = f"[Booking {reservation.code}] {subject}"

                send_mail(
                    email_subject,
                    body,
                    None,
                    [reservation.email],
                    fail_silently=False,
                )     
            except Exception as exc:
                entry.delivery = GuestConversationMessage.Delivery.FAILED
                entry.error = type(exc).__name__[:120]
                entry.save(update_fields=['delivery', 'error'])
                messages.warning(request, 'Message saved in SummitDesk, but email sending failed. Check SMTP settings.')
            else:
                entry.delivery = GuestConversationMessage.Delivery.SENT
                entry.save(update_fields=['delivery'])
                messages.success(request, 'Message saved and submitted to the configured email backend.')
        else:
            messages.success(request, 'Message saved in the guest conversation (no email sent).')
        return redirect('bookings:conversation_thread', code=code)

    conversation = list(GuestConversationMessage.objects.filter(
        reservation=reservation, hut=hut).select_related('sent_by').order_by('-created_at')[:100])
    automated = list(GuestMessageLog.objects.filter(
        reservation=reservation, hut=hut).order_by('-created_at')[:50])
    timeline = (
        [{'kind': 'conversation', 'created_at': e.created_at, 'message': e} for e in conversation]
        + [{'kind': 'automated', 'created_at': e.created_at, 'message': e} for e in automated]
    )
    timeline.sort(key=lambda e: (e['created_at'], e['message'].pk))
    return render(request, 'bookings/conversation_thread_v134.html', {
        'reservation': reservation, 'hut': hut, 'timeline': timeline[-120:],
        'presets': _presets(reservation, hut),
    })


@staff_member_required
@never_cache
@require_http_methods(['GET', 'POST'])
def quick_replies(request):
    huts, selected_hut, selected_slug = permitted_hut_selection(request)
    if request.method == 'POST':
        hut_id = request.POST.get('hut_id', '')
        if not hut_id.isdecimal():
            raise Http404
        hut = get_object_or_404(huts, pk=hut_id)
        if selected_hut and selected_hut.pk != hut.pk:
            raise Http404
        reply_id = request.POST.get('reply_id', '').strip()
        if reply_id and not reply_id.isdecimal():
            raise Http404
        existing = get_object_or_404(HutQuickReply, hut=hut, pk=reply_id) if reply_id else None
        title = request.POST.get('title', '').strip()
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        try:
            if not (1 <= len(title) <= 80):
                raise ValueError('Quick reply name must be 1–80 characters.')
            if not (1 <= len(subject) <= 200) or not (1 <= len(body) <= 4000):
                raise ValueError('Subject or message length is invalid.')
            if '\r' in subject or '\n' in subject:
                raise ValueError('Subject cannot contain line breaks.')
            validate_text(subject)
            validate_text(body)
            duplicates = HutQuickReply.objects.filter(hut=hut, title=title)
            if existing:
                duplicates = duplicates.exclude(pk=existing.pk)
            if duplicates.exists():
                raise ValueError('A quick reply with this name already exists for this hut.')
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(reverse('bookings:quick_replies') + '?hut=' + hut.slug)
        if not existing:
            existing = HutQuickReply(hut=hut)
        existing.title, existing.subject, existing.body = title, subject, body
        existing.enabled = request.POST.get('enabled') == 'on'
        existing.save()
        messages.success(request, 'Quick reply saved.')
        return redirect(reverse('bookings:quick_replies') + '?hut=' + hut.slug)

    replies = HutQuickReply.objects.filter(hut__in=huts).select_related('hut')
    if selected_hut:
        replies = replies.filter(hut=selected_hut)
    return render(request, 'bookings/quick_replies_v134.html', {
        'huts': huts, 'selected_hut': selected_hut, 'selected_slug': selected_slug,
        'replies': replies, 'builtin_replies': BUILTIN_REPLIES,
    })


@never_cache
@require_POST
def guest_send_message(request, token):
    reservation = guest_reservation(token)  # Revocation and token checked on every POST.
    hut = _hut_for_reservation(reservation)
    if reservation.check_out < timezone.localdate() - timedelta(days=7):
        messages.error(request, 'Messaging for this stay has closed.')
        return redirect('bookings:guest_self_service', token=token)
    body = request.POST.get('body', '').strip()
    if not body or len(body) > 2000:
        messages.error(request, 'Enter a message of 1–2000 characters.')
        return redirect('bookings:guest_self_service', token=token)
    # Per-reservation rate limiting prevents a leaked link being used for flooding.
    with transaction.atomic():
        locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
        recent = GuestConversationMessage.objects.filter(
            reservation=locked, sender=GuestConversationMessage.Sender.GUEST,
            created_at__gte=timezone.now() - timedelta(hours=1)).count()
        if recent >= 5:
            messages.error(request, 'Too many messages. Please try again in an hour.')
            return redirect('bookings:guest_self_service', token=token)
        GuestConversationMessage.objects.create(
            reservation=locked, hut=hut,
            sender=GuestConversationMessage.Sender.GUEST,
            body=body, delivery=GuestConversationMessage.Delivery.RECEIVED,
        )
    messages.success(request, 'Your message was saved. The hut team can read it in SummitDesk.')
    return redirect('bookings:guest_self_service', token=token)
