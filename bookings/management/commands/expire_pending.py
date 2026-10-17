from django.core.management.base import BaseCommand

from bookings.services import expire_pending


class Command(BaseCommand):
    help = "Release beds held by unpaid (pending) reservations. Run from cron every few minutes."

    def handle(self, *args, **options):
        self.stdout.write(f"Cancelled {expire_pending()} expired reservation(s).")
