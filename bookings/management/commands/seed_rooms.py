from django.core.management.base import BaseCommand

from bookings.models import Room

SAMPLE = [
    ("Dormitory", "Shared bunk room", 12, "15.00"),
    ("Room 1", "Four-bed room", 4, "20.00"),
    ("Room 2", "Four-bed room", 4, "20.00"),
]


class Command(BaseCommand):
    help = "Create a few sample rooms so the booking page has something to show."

    def handle(self, *args, **options):
        for position, (name, description, capacity, price) in enumerate(SAMPLE):
            _, created = Room.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "capacity": capacity,
                    "price_per_night": price,
                    "position": position,
                },
            )
            self.stdout.write(f"{'Created' if created else 'Kept'} {name}")
