"""Read-only, hut-scoped daily operations filters and CSV exports."""
from .operations_v58_v62 import csv_response

def search_issues(issues, query):
    q = (query or '').strip()[:100].casefold()
    return [i for i in issues if not q or q in ' '.join(str(i.get(k, '')) for k in ('title','detail','day','kind')).casefold()]

def select_readiness(rows, mode):
    return [r for r in rows if mode != 'review' or r['needs_review']]

def issues_csv(hut, rows):
    data = ((r['day'].isoformat(),r['kind'],r['title'],r['detail']) for r in rows)
    return csv_response(f'critical_issues_hut_{hut.pk}.csv', ('Date','Type','Issue','Details'), data)

def readiness_csv(hut, rows):
    data = ((r['day'].isoformat(),r['groups'],r['bed_places'],r['unassigned'],r['cleaning'],
             'Needs review' if r['needs_review'] else 'No detected issues') for r in rows)
    return csv_response(f'arrival_readiness_hut_{hut.pk}.csv',
        ('Date','Arrival groups','Bed places','Unassigned','Unfinished cleaning tasks','Review status'),data)
