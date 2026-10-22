"""Hut-scoped read-only daily workspace reporting helpers."""
from collections import Counter
from .operations_v58_v62 import csv_response

ISSUE_KINDS = ('all', 'Conflict', 'Arrival')

def filter_issues(issues, kind='all'):
    if kind not in ISSUE_KINDS:
        kind = 'all'
    return [i for i in issues if kind == 'all' or i['kind'] == kind]

def arrival_readiness(timeline):
    result = []
    for group in timeline:
        arrivals = group['arrivals']
        unassigned = sum(int(a['unassigned']) for a in arrivals)
        cleaning = sum(int(a['open_tasks']) for a in arrivals)
        result.append({'day':group['day'], 'groups':len(arrivals),
                       'bed_places':sum(int(a['beds']) for a in arrivals),
                       'unassigned':unassigned, 'cleaning':cleaning,
                       'needs_review':bool(unassigned or cleaning)})
    return result

def bed_details_csv(hut, daily):
    rows = ((row['room'], row['number'], night['day'].isoformat(), night['label'])
            for row in daily['bed_rows'] for night in row['nights'])
    return csv_response(f'numbered_beds_hut_{hut.pk}.csv',
                        ('Room','Bed number','Date','Recorded status'), rows)

def checklist_csv(hut, daily):
    rows = ((row['day'].isoformat(),row['conflicts'],row['unassigned'],
             row['cleaning'],'No detected issues' if row['clear'] else 'Needs review')
            for row in daily['checklist'])
    return csv_response(f'daily_checklist_hut_{hut.pk}.csv',
                        ('Date','Conflicts','Unassigned bed places',
                         'Unfinished cleaning tasks','Review status'),rows)
