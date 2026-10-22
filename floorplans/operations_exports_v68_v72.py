"""v68-v72: CSV exports and manager action filtering. No writes."""
from .operations_v58_v62 import csv_response

EXPORT_TYPES = ('conflicts', 'availability', 'arrivals', 'actions')
PRIORITIES = {'all': None, 'conflicts': 0, 'assignments': 1, 'cleaning': 2}


def filter_actions(actions, priority):
    selected = PRIORITIES.get(priority)
    if selected is None:
        return list(actions)
    return [a for a in actions if a['priority'] == selected]


def operations_csv(hut, ops, kind, actions=None):
    """Export existing hut-scoped computed data, never recompute without access checks."""
    if kind not in EXPORT_TYPES:
        raise ValueError('Unsupported operations export')
    if kind == 'conflicts':
        headings = ('Date', 'Room', 'Conflict', 'Details')
        rows = ((w['day'].isoformat(), w['room'], w['kind'], w['detail']) for w in ops['conflicts'])
    elif kind == 'availability':
        headings = ('Date', 'Room', 'Confirmed beds', 'Pending beds', 'Usable beds',
                    'Free beds', 'Closed beds', 'Capacity status')
        rows = ((n['day'].isoformat(), r['room'], n['confirmed'], n['pending'],
                 n['usable'], n['free'], n['closed'], n['status'])
                for r in ops['calendar'] for n in r['nights'])
    elif kind == 'arrivals':
        headings = ('Date', 'Room', 'Arriving bed places', 'Unassigned bed places',
                    'Unfinished cleaning tasks')
        rows = ((a['day'].isoformat(), a['room'], a['beds'], a['unassigned'], a['open_tasks'])
                for a in ops['arrivals'])
    else:
        headings = ('Date', 'Priority', 'Action', 'Details')
        priority_names = {0: 'Conflict', 1: 'Bed assignment', 2: 'Cleaning'}
        rows = ((a['day'].isoformat(), priority_names.get(a['priority'], 'Other'),
                 a['label'], a['detail']) for a in (actions if actions is not None else ops['actions']))
    return csv_response(f'manager_{kind}_hut_{hut.pk}.csv', headings, rows)
