from django.core.management.base import BaseCommand
from django.utils import timezone
from bookings.models import ReservationNotification
from bookings.notifications_v145 import MAX_ATTEMPTS, deliver_notification


class Command(BaseCommand):
    help = 'Retry due reservation notifications. Defaults to a dry run; --apply sends email.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], 500))
        ids = list(ReservationNotification.objects.filter(status__in=['pending', 'failed'],
                   attempts__lt=MAX_ATTEMPTS, next_attempt_at__lte=timezone.now())
                   .order_by('next_attempt_at', 'pk').values_list('pk', flat=True)[:limit])
        self.stdout.write(f'Due notifications: {len(ids)}; mode: {"SEND" if options["apply"] else "DRY RUN"}')
        if options['apply']:
            outcomes = [deliver_notification(pk) for pk in ids]
            self.stdout.write(f'Sent: {outcomes.count("sent")}; failed: {outcomes.count("failed")}')
