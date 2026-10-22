"""Read-only hut-scoped operational details for managers."""
from collections import defaultdict
from datetime import timedelta
from bookings.models import Bed, BedAssignment, BedClosure, ReservationItem, Room


def build_daily_workspace(hut, start, ops):
    finish = start + timedelta(days=7)
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('name', 'pk'))
    room_ids = [r.pk for r in rooms]
    beds = list(Bed.objects.filter(room_id__in=room_ids).select_related('room').order_by('room__name','number'))
    items = list(ReservationItem.objects.filter(room_id__in=room_ids,
        reservation__status__in=('confirmed','pending'),
        reservation__check_in__lt=finish, reservation__check_out__gt=start
    ).select_related('reservation'))
    assignments = list(BedAssignment.objects.filter(item__in=items).select_related('bed'))
    closures = list(BedClosure.objects.filter(bed__room_id__in=room_ids,
        start__lt=finish, end__gt=start))
    assigned = defaultdict(list)
    for a in assignments:
        assigned[a.bed_id].append(a.item)
    closed = defaultdict(list)
    for c in closures:
        closed[c.bed_id].append(c)
    by_room = defaultdict(list)
    for b in beds:
        by_room[b.room_id].append(b)
    days = [start + timedelta(days=i) for i in range(7)]
    bed_rows = []
    for room in rooms:
        for bed in by_room[room.pk]:
            nights = []
            for day in days:
                active = [i for i in assigned[bed.pk]
                          if i.reservation.check_in <= day < i.reservation.check_out]
                is_closed = any(c.start <= day < c.end for c in closed[bed.pk])
                if (is_closed and active) or len({i.pk for i in active}) > 1:
                    status, label = 'conflict', 'Conflict'
                elif is_closed:
                    status, label = 'closed', 'Closed'
                elif active:
                    status = 'pending' if all(i.reservation.status == 'pending' for i in active) else 'occupied'
                    label = 'Held' if status == 'pending' else 'Assigned'
                else:
                    # Unassigned reservations may still need this bed.
                    status, label = 'unassigned', 'Unassigned'
                nights.append({'day':day,'status':status,'label':label})
            bed_rows.append({'room':room.name,'number':bed.number,'nights':nights})
    urgent = []
    for w in ops['conflicts']:
        urgent.append({'day':w['day'],'title':w['kind'],'detail':w['room']+' — '+w['detail'], 'kind':'Conflict'})
    for a in ops['arrivals']:
        if a['unassigned'] or a['open_tasks']:
            issues=[]
            if a['unassigned']:
                issues.append(str(a['unassigned'])+' unassigned places')
            if a['open_tasks']:
                issues.append(str(a['open_tasks'])+' unfinished cleaning tasks')
            urgent.append({'day':a['day'],'title':'Arrival preparation',
                           'detail':a['room']+' — '+', '.join(issues),'kind':'Arrival'})
    urgent.sort(key=lambda x:(x['day'],x['kind'],x['detail']))
    timeline=defaultdict(list)
    for a in ops['arrivals']:
        timeline[a['day']].append(a)
    arrivals_by_day=[{'day':d,'arrivals':timeline[d]} for d in days]
    checklist=[]
    for d in days:
        conflicts=[w for w in ops['conflicts'] if w['day']==d]
        arrivals=timeline[d]
        unassigned=sum(a['unassigned'] for a in arrivals)
        cleaning=sum(a['open_tasks'] for a in arrivals)
        checklist.append({'day':d,'conflicts':len(conflicts), 'unassigned':unassigned,
                          'cleaning':cleaning, 'clear':not(conflicts or unassigned or cleaning)})
    return {'urgent':urgent, 'timeline':arrivals_by_day, 'bed_rows':bed_rows,
            'checklist':checklist,'urgent_count':len(urgent),
            'beds_count':len(bed_rows), 'days':days}
