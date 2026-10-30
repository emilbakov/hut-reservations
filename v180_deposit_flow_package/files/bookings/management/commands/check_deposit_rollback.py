from django.core.management.base import BaseCommand, CommandError
from bookings.models import ReservationDepositRequest
class Command(BaseCommand):
    help = 'Refuse legacy source rollback while approved v180 holds are active.'
    def handle(self,*args,**options):
        count=ReservationDepositRequest.objects.filter(state__in=['awaiting','review'],reservation__status='pending').count()
        if count:
            raise CommandError(f'{count} active approved deposit holds remain. Resolve or withdraw them in v180 before rolling back; no records were changed.')
        self.stdout.write('Deposit rollback preflight passed; no active approved holds.')
