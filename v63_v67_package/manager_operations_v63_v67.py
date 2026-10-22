"""SummitDesk v63-v67 read-only manager operations page."""
from collections import defaultdict
from datetime import timedelta
from bookings.models import Bed, Room
from .operations_v58_v62 import build_room_operations

def build_manager_operations(hut, start):
    base = build_room_operations(hut, start)
    rooms = list(Room.objects.filter(hut=hut, is_active=True).order_by('name','pk'))
    room_names = [r.name for r in rooms]
    numbered = defaultdict(list)
    for bed in Bed.objects.filter(room__in=rooms).select_related('room').order_by('room__name','number'):
        numbered[bed.room.name].append(bed.number)
    matrix = defaultdict(dict)
    for row in base['rooms']:
        matrix[row['room']][row['day']] = row
    dates = [start + timedelta(days=i) for i in range(7)]
    calendar = []
    for name in room_names:
        nights = []
        for day in dates:
            r = matrix[name].get(day)
            if not r:
                continue
            status = ('over' if r['confirmed'] + r['pending'] > r['usable']
                      else 'closed' if r['usable'] == 0
                      else 'full' if r['free'] == 0
                      else 'limited' if r['free'] <= 2 else 'available')
            nights.append(dict(r, status=status))
        calendar.append({'room':name, 'numbered_beds':numbered[name], 'nights':nights})
    conflicts = [w for w in base['warnings'] if w['kind'] in (
        'Overlapping bed assignments','Assigned bed closed','Wrong-room assignment',
        'Excess bed assignments','Room capacity exceeded')]
    actions = []
    for w in conflicts:
        actions.append({'day':w['day'], 'priority':0, 'label':'Resolve '+w['kind'],
                        'detail':w['room']+' — '+w['detail']})
    for a in base['arrivals']:
        if a['unassigned']:
            actions.append({'day':a['day'], 'priority':1, 'label':'Assign beds before arrival',
                            'detail':f"{a['room']} — {a['unassigned']} unassigned bed places"})
        if a['open_tasks']:
            actions.append({'day':a['day'], 'priority':2, 'label':'Review arrival cleaning',
                            'detail':f"{a['room']} — {a['open_tasks']} unfinished tasks"})
    actions.sort(key=lambda a:(a['priority'], a['day'], a['label'], a['detail']))
    return {'dates':dates, 'calendar':calendar, 'conflicts':conflicts,
            'arrivals':base['arrivals'], 'actions':actions,
            'conflict_count':len(conflicts), 'arrival_count':len(base['arrivals']),
            'action_count':len(actions), 'room_count':len(rooms)}
