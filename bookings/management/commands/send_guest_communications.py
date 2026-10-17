from django.core.management.base import BaseCommand
from bookings.communications import run_communications

class Command(BaseCommand):
    help = "Preview guest emails; --send delivers due/overdue deposit and pre-arrival emails."

    def add_arguments(self, parser):
        parser.add_argument("--send", action="store_true", help="Actually send emails; otherwise preview only")
        parser.add_argument("--include-cancellations", action="store_true",
                            help="Also send one cancellation email per future arrival date")

    def handle(self, *args, **options):
        result = run_communications(
            dry_run=not options["send"],
            include_cancellations=options["include_cancellations"],
        )
        self.stdout.write(", ".join(f"{key}: {value}" for key, value in result.items()))
