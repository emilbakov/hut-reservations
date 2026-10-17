"""Run from Django project root; backs up each changed file."""
from pathlib import Path
import shutil
from datetime import datetime

root = Path.cwd()
models = root / 'bookings/models.py'
services = root / 'bookings/services.py'
urls = root / 'bookings/urls.py'
calendar = root / 'bookings/room_calendar.py'
for path in (models, services, urls, calendar):
    if not path.is_file():
        raise SystemExit(f'Missing {path}; no changes made')
if 'class Bed(models.Model)' in models.read_text():
    raise SystemExit('Bed models already exist. Stop to avoid conflicting edits.')
if 'def free_beds(rooms, check_in, check_out, exclude=None):' not in services.read_text():
    raise SystemExit('Unexpected services.py layout; no changes made')
if 'urlpatterns' not in urls.read_text():
    raise SystemExit('Unexpected urls.py layout; no changes made')

stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for path in (models, services, urls, calendar):
    shutil.copy2(path, path.with_name(path.name + '.before_beds_' + stamp))

new_models = '''

class Bed(models.Model):
    """A numbered physical bed. A room's capacity remains the booking limit."""
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='individual_beds')
    number = models.PositiveIntegerField()

    class Meta:
        ordering = ['room_id', 'number']
        constraints = [models.UniqueConstraint(fields=['room', 'number'], name='unique_numbered_bed_per_room')]

    def __str__(self):
        return f'{self.room} / Bed {self.number}'


class BedAssignment(models.Model):
    """A bed assigned to one reservation item for the reservation's full stay."""
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name='assignments')
    item = models.ForeignKey(ReservationItem, on_delete=models.CASCADE, related_name='bed_assignments')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['bed', 'item'], name='unique_bed_assignment_item')]


class BedClosure(models.Model):
    """Bed unavailable on nights in [start, end)."""
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name='closures')
    start = models.DateField()
    end = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(end__gt=F('start')), name='bed_closure_end_after_start')]
'''
models.write_text(models.read_text() + new_models)

src = services.read_text()
src = src.replace('from .models import Reservation, ReservationItem, Room', 'from .models import BedClosure, Reservation, ReservationItem, Room')
needle = '    return {\n        room.pk: max(\n            room.capacity - max(\n                booked[room.pk].values(),\n                default=0,\n            ),\n            0,\n        )\n        for room in rooms\n    }'
replacement = '''    # Maintenance closures reduce physical capacity on each night, not merely
    # the number of unassigned beds. Preserve the original quantity booking model.
    room_list = list(rooms)
    closures = BedClosure.objects.filter(
        bed__room__in=room_list, start__lt=check_out, end__gt=check_in,
    ).values_list('bed__room_id', 'bed_id', 'start', 'end')
    blocked = defaultdict(lambda: defaultdict(set))
    for room_id, bed_id, start, end in closures:
        night = max(start, check_in)
        last = min(end, check_out)
        while night < last:
            blocked[room_id][night].add(bed_id)
            night += timedelta(days=1)
    result = {}
    for room in room_list:
        available = room.capacity
        night = check_in
        while night < check_out:
            available = min(available, room.capacity - booked[room.pk][night] - len(blocked[room.pk][night]))
            night += timedelta(days=1)
        result[room.pk] = max(available, 0)
    return result'''
if needle not in src:
    raise SystemExit('Unexpected free_beds implementation; restore models.py from backup before retrying.')
src = src.replace(needle, replacement)
# Existing bed assignments are tied to ReservationItem and cascade when items are
# deleted by modify_reservation. Explicitly avoid changing that established flow.
services.write_text(src)

url_text = urls.read_text()
url_text += '''\n# Individual bed management\nfrom .bed_management import bed_management\nurlpatterns += [\n    path('staff/rooms/<int:room_id>/beds/', bed_management, name='bed_management'),\n]\n'''
urls.write_text(url_text)

cal = calendar.read_text()
# Add a link for each room without changing the calendar's occupancy logic.
cal = cal.replace('from .models import Hut, Reservation, ReservationItem, Room', 'from .models import BedClosure, Hut, Reservation, ReservationItem, Room')
cal = cal.replace('    rows = []', """    closures = list(BedClosure.objects.filter(
        bed__room_id__in=room_ids, start__lt=end, end__gt=first
    ).values_list('bed__room_id', 'bed_id', 'start', 'end'))
    rows = []""")
cal = cal.replace('            free = max(room.capacity - occupied, 0) if room.is_active else 0', """            blocked = len({bed_id for room_id, bed_id, start, stop in closures
                           if room_id == room.pk and start <= day < stop})
            free = max(room.capacity - occupied - blocked, 0) if room.is_active else 0""")
cal = cal.replace('"is_empty": occupied == 0 and room.is_active', '"is_empty": occupied == 0 and blocked == 0 and room.is_active')
calendar.write_text(cal)

calendar_template = root / 'bookings/templates/bookings/room_calendar.html'
if calendar_template.exists():
    shutil.copy2(calendar_template, calendar_template.with_name(calendar_template.name + '.before_beds_' + stamp))
    t = calendar_template.read_text()
    target = '{{ row.room.name }}<br><small>'
    if target in t and "'bookings:bed_management'" not in t:
        replacement = "{{ row.room.name }}<br><a href=\"{% url 'bookings:bed_management' row.room.pk %}?day={{ today|date:'Y-m-d' }}\">Manage beds</a><br><small>"
        t = t.replace(target, replacement, 1)
        calendar_template.write_text(t)
    else:
        print('Calendar template not modified; add a Manage beds link manually.')

src_dir = Path(__file__).resolve().parent / 'bookings'
for rel in ['bed_management.py', 'templates/bookings/bed_management.html']:
    dst = root / 'bookings' / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise SystemExit(f'{dst} already exists; inspect before overwriting.')
    shutil.copy2(src_dir / rel, dst)
print('Installed models, service availability logic, staff URL, and bed management template.')
print('Backups end with:', '.before_beds_' + stamp)
print('NEXT: python manage.py makemigrations bookings && python manage.py migrate')
