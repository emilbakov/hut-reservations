from django.core.management.base import BaseCommand
from django.db import transaction
from bookings.models import Bed
from floorplans.models import RoomPlacement, BedMarker

class Command(BaseCommand):
    help = 'One-time safe migration of coordinate-only markers to physical Bed IDs.'

    @transaction.atomic
    def handle(self, *args, **options):
        created = skipped = 0
        for placement in RoomPlacement.objects.all().iterator():
            positions = placement.bed_positions
            if not isinstance(positions, list):
                continue
            beds = list(Bed.objects.filter(room_id=placement.room_id).order_by('number', 'pk'))
            occupied = set(BedMarker.objects.filter(bed__room_id=placement.room_id).values_list('x', 'y'))
            for bed, pos in zip(beds, positions):
                if BedMarker.objects.filter(bed=bed).exists():
                    skipped += 1
                    continue
                if not isinstance(pos, dict):
                    continue
                x, y = pos.get('x'), pos.get('y')
                if type(x) is not int or type(y) is not int or not (0 <= x < 8 and 0 <= y < 6) or (x, y) in occupied:
                    skipped += 1
                    continue
                BedMarker.objects.create(bed=bed, x=x, y=y)
                occupied.add((x, y)); created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} permanent markers; skipped {skipped}. Existing markers preserved.'))
