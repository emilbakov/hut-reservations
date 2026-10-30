from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST


@login_required
@require_POST
def withdraw_deposit(request, code):
    from .views import get_locked_manageable_reservation
    from .deposit_flow_v180 import awaiting, expire_hold, queue_hold_email
    from .models import ReservationDecision
    from .staff_decisions_v152 import fingerprint
    reason = request.POST.get('reason', '').strip()
    if not reason or len(reason) > 1000:
        messages.error(request, _('Enter a withdrawal reason of 1–1,000 characters.'))
        return redirect('bookings:reservation_payments', code=code)
    with transaction.atomic():
        reservation = get_locked_manageable_reservation(request.user, code=code)
        if not awaiting(reservation):
            messages.error(request, _('Only an unpaid deposit request can be withdrawn.'))
        elif expire_hold(reservation, reservation.deposit_request):
            messages.error(request, _('The deadline has passed; the unpaid hold was released.'))
        else:
            hold = reservation.deposit_request
            hold.state, hold.closed_at, hold.closed_by = 'withdrawn', timezone.now(), request.user
            hold.close_reason = reason
            hold.save(update_fields=['state', 'closed_at', 'closed_by', 'close_reason'])
            ReservationDecision.objects.create(reservation=reservation, actor=request.user, before='pending', after='pending',
                reason='Deposit approval withdrawn: '+reason, fingerprint=fingerprint(reservation))
            queue_hold_email(hold, 'deposit_withdrawn_guest')
            messages.success(request, _('Deposit approval withdrawn. Review the stay and issue new terms before requesting payment again.'))
    return redirect('bookings:reservation_payments', code=code)
