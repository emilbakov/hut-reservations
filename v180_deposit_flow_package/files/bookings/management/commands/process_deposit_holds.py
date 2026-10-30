from django.core.management.base import BaseCommand
from bookings.deposit_flow_v180 import process_holds

class Command(BaseCommand):
    help = 'Release elapsed v180 deposit holds and queue pre-deadline reminders. No SMTP work.'
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
    def handle(self, *args, **options):
        result = process_holds(dry_run=options['dry_run'])
        self.stdout.write(f'Deposit holds: expired={result["expired"]}; reminders={result["reminders"]}; blocked={result["blocked"]}; dry_run={options["dry_run"]}')
