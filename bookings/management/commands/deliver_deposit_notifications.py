from django.core.management.base import BaseCommand
from django.utils import timezone
from bookings.models import ReservationNotification
from bookings.notifications_v145 import deliver_notification, MAX_ATTEMPTS

class Command(BaseCommand):
    help = 'Deliver/retry due notifications for bookings using v180 deposit requests.'
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10)
    def handle(self, *args, **options):
        kinds=['deposit_request_guest','deposit_reminder_guest','deposit_expired_guest',
               'deposit_withdrawn_guest','deposit_review_guest','deposit_review_manager','confirmation_guest','confirmation_manager',
               'declined_guest','decision_undo_guest']
        ids=list(ReservationNotification.objects.filter(reservation__deposit_request__isnull=False,
            kind__in=kinds,status__in=['pending','failed'],attempts__lt=MAX_ATTEMPTS,
            next_attempt_at__lte=timezone.now()).order_by('pk').values_list('pk',flat=True)[:max(0,min(100,options['limit']))])
        results={}
        for pk in ids:
            state=deliver_notification(pk);results[state]=results.get(state,0)+1
        self.stdout.write('Deposit notification delivery: '+str(results))
