"""Run daily with cron: python manage.py send_deposit_reminders."""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from bookings.deposits import deposit_summary
from bookings.models import DepositReminderLog, Reservation


class Command(BaseCommand):
    help = 'Send one overdue-deposit reminder per reservation and due date.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        sent = skipped = 0
        candidates = Reservation.objects.filter(status__in=Reservation.HOLDING).exclude(email='').values_list('pk', flat=True)
        for pk in candidates.iterator():
            with transaction.atomic():
                reservation = Reservation.objects.select_for_update().get(pk=pk)
                summary = deposit_summary(reservation)
                if not summary or not summary['overdue'] or not summary['reminders_enabled']:
                    skipped += 1
                    continue
                if DepositReminderLog.objects.filter(reservation=reservation, due_date=summary['due_date']).exists():
                    skipped += 1
                    continue
                if options['dry_run']:
                    self.stdout.write(f'Would remind reservation {reservation.code}')
                    continue
                # Record under the reservation lock. On send failure the DB
                # transaction rolls back, so a future run can retry.
                DepositReminderLog.objects.create(reservation=reservation, due_date=summary['due_date'])
                send_mail(
                    'Deposit payment reminder',
                    f'Hello {reservation.name},\n\n'
                    f'Your reservation {reservation.code} has a deposit balance of '
                    f'{summary["remaining"]} {settings.BOOKING_CURRENCY} '
                    f'which was due on {summary["due_date"]}.\n'
                    'Please contact the mountain hut to arrange payment.\n',
                    None, [reservation.email], fail_silently=False,
                )
                sent += 1
        self.stdout.write(self.style.SUCCESS(f'Deposit reminders sent: {sent}; skipped: {skipped}'))
