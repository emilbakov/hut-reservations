"""SummitDesk v58-v62: read-only, hut-scoped operational detail."""
import csv
from collections import defaultdict
from datetime import timedelta
from django.http import HttpResponse
from bookings.models import Room, ReservationItem, BedClosure, BedAssignment
from .housekeeping_tasks import HousekeepingTask


def safe_cell(value):
    value = str(value if value is not None else '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


def csv_response(filename, headings, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(headings)
    for row in rows:
        writer.writerow([safe_cell(x) for x in row])
    return response


def capacity_csv(hut, rows):
    return csv_response(f'capacity_warnings_hut_{hut.pk}.csv',
        ['Date', 'Severity', 'Description', 'Confirmed beds', 'Pending beds', 'Usable capacity', 'Free beds'],
        [(x['day'].isoformat(), x['severity'], x['message'], x['confirmed'], x['pending'], x['usable'], x['free']) for x in rows])


def build_room_operations(hut, start):
    """Seven-night room totals; bed assignment and closure conflicts are independent warnings."""
    finish = start + timedelta(days=7)
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('name', 'pk'))
    room_ids = [r.pk for r in rooms]
    items = list(ReservationItem.objects.filter(room_id__in=room_ids,
        reservation__status__in=('confirmed', 'pending'),
        reservation__check_in__lt=finish, reservation__check_out__gt=start
    ).select_related('reservation', 'room'))
    closures = list(BedClosure.objects.filter(bed__room_id__in=room_ids,
        start__lt=finish, end__gt=start).select_related('bed'))
    assignments = list(BedAssignment.objects.filter(item__in=items).select_related('bed', 'item__reservation'))
    tasks = list(HousekeepingTask.objects.filter(bed__room_id__in=room_ids,
        day__gte=start, day__lt=finish).select_related('bed'))
    assigned_by_item = defaultdict(list)
    for assignment in assignments:
        assigned_by_item[assignment.item_id].append(assignment)
    close_by_bed_day = set()
    for closure in closures:
        day = max(start, closure.start)
        while day < min(finish, closure.end):
            close_by_bed_day.add((closure.bed_id, day))
            day += timedelta(days=1)
    task_by_room_day = defaultdict(list)
    for task in tasks:
        task_by_room_day[(task.bed.room_id, task.day)].append(task)
    results, warnings, arrivals = [], [], []
    for room in rooms:
        room_items = [i for i in items if i.room_id == room.pk]
        room_beds = {a.bed_id for i in room_items for a in assigned_by_item[i.pk]}
        for offset in range(7):
            day = start + timedelta(days=offset)
            active = [i for i in room_items if i.reservation.check_in <= day < i.reservation.check_out]
            confirmed = sum(i.beds for i in active if i.reservation.status == 'confirmed')
            pending = sum(i.beds for i in active if i.reservation.status == 'pending')
            closed = len({c.bed_id for c in closures if c.bed.room_id == room.pk and c.start <= day < c.end})
            usable = max(0, room.capacity - closed)
            free = max(0, usable - confirmed - pending)
            results.append({'day': day, 'room': room.name, 'confirmed': confirmed,
                'pending': pending, 'usable': usable, 'free': free, 'closed': closed})
            if confirmed + pending > usable:
                warnings.append({'day': day, 'room': room.name, 'kind': 'Room capacity exceeded',
                    'detail': f'{confirmed + pending} reserved/held; {usable} usable'})
            assigned_beds = defaultdict(set)
            for item in active:
                assigned = assigned_by_item[item.pk]
                if len(assigned) > item.beds:
                    warnings.append({'day': day, 'room': room.name, 'kind': 'Excess bed assignments',
                        'detail': f'Reservation item {item.pk}: {len(assigned)} assigned, {item.beds} booked'})
                for a in assigned:
                    if a.bed.room_id != room.pk:
                        warnings.append({'day': day, 'room': room.name, 'kind': 'Wrong-room assignment',
                            'detail': f'Item {item.pk}, bed {a.bed_id}'})
                    assigned_beds[a.bed_id].add(item.pk)
                    if (a.bed_id, day) in close_by_bed_day:
                        warnings.append({'day': day, 'room': room.name, 'kind': 'Assigned bed closed',
                            'detail': f'Bed {a.bed.number}, item {item.pk}'})
            for bed_id, item_ids in assigned_beds.items():
                if len(item_ids) > 1:
                    warnings.append({'day': day, 'room': room.name, 'kind': 'Overlapping bed assignments',
                        'detail': f'Bed ID {bed_id}, items {", ".join(map(str, sorted(item_ids)))}'})
            incoming = [i for i in room_items if i.reservation.check_in == day and i.reservation.status == 'confirmed']
            if incoming:
                outstanding = sum(1 for t in task_by_room_day[(room.pk, day)] if t.status != 'done')
                unassigned = sum(max(0, i.beds - len(assigned_by_item[i.pk])) for i in incoming)
                arrivals.append({'day': day, 'room': room.name,
                    'beds': sum(i.beds for i in incoming), 'open_tasks': outstanding,
                    'unassigned': unassigned})
    warnings.sort(key=lambda w: (w['day'], w['room'], w['kind']))
    arrivals.sort(key=lambda a: (a['day'], a['room']))
    return {'rooms': results, 'warnings': warnings, 'arrivals': arrivals,
            'room_count': len(rooms), 'warning_count': len(warnings)}
