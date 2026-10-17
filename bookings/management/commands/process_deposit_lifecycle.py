from django.core.management.base import BaseCommand
from bookings.lifecycle import process_lifecycle

class Command(BaseCommand):
    help = "Record overdue-deposit warnings; cancellation requires explicit --allow-cancellation and per-hut opt-in."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--allow-cancellation", action="store_true")

    def handle(self, *args, **options):
        result = process_lifecycle(
            dry_run=options["dry_run"], allow_cancellation=options["allow_cancellation"],
            output=self.stdout.write,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Warnings: {result["warnings"]}; cancellations: {result["cancellations"]}; skipped: {result["skipped"]}'
        ))
