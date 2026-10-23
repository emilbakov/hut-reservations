"""Private-link recovery and property-scoped email delivery controls."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import GuestAccessLink, ReservationNotification
from .notifications_v145 import deliver_notification, queue_notification


@require_http_methods(['GET', 'POST'])
def recover_guest_link(request, reservation):
    if request.method == 'POST':
        access = GuestAccessLink.objects.filter(reservation=reservation).first()
        # Revoked access stays revoked. Only explicit manager reissue restores it.
        if reservation.email and not (access and access.revoked_at):
            from .self_service import issue_guest_link
            link = request.build_absolute_uri(issue_guest_link(reservation))
            # Database uniqueness limits recovery sends across all workers.
            window = int(timezone.now().timestamp()) // 900
            queue_notification(reservation, 'access_guest', 'Your private reservation link',
                               'Use this private link to view your reservation and request changes:\n' + link +
                               '\nKeep this link private. Anyone with it can view your booking.\n',
                               reservation.email, event=str(window))
        messages.info(request, 'If online access is available, a private link will be emailed to the booking address. Otherwise, contact the hut for assistance.')
        return redirect(request.path)
    return render(request, 'bookings/private_link_v145.html')


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def notification_deliveries(request):
    from .views import manageable_reservations, permitted_hut_selection
    huts, hut, slug = permitted_hut_selection(request)
    allowed = manageable_reservations(request.user)
    if hut:
        allowed = allowed.filter(items__room__hut=hut).distinct()
    deliveries = ReservationNotification.objects.filter(reservation__in=allowed)
    if request.method == 'POST':
        item = get_object_or_404(deliveries, pk=request.POST.get('notification_id'))
        if request.POST.get('action') != 'retry':
            raise PermissionDenied('Unknown delivery action.')
        status = deliver_notification(item.pk, manual=True)
        if status == 'sent':
            messages.success(request, 'Email sent. The reservation was not changed.')
        elif status == 'skipped':
            messages.info(request, 'This notification is no longer needed. The reservation was not changed.')
        else:
            messages.error(request, 'Email delivery failed. Check the email configuration and retry later.')
        from django.urls import reverse
        from urllib.parse import urlencode
        url = reverse('bookings:notification_deliveries')
        return redirect(url + ('?' + urlencode({'hut': slug}) if slug else ''))
    failed = deliveries.filter(status='failed').count()
    return render(request, 'bookings/notification_deliveries_v145.html', {
        'deliveries': deliveries.select_related('reservation').order_by('-created_at')[:100],
        'failed_count': failed, 'huts': huts, 'selected_hut': hut, 'selected_slug': slug,
    })
