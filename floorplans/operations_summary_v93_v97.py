"""Manager Operations summary helpers (read-only)."""
from .operations_v58_v62 import csv_response

def sort_issues(rows, mode):
    if mode == 'latest': return sorted(rows,key=lambda r:r['day'],reverse=True)
    if mode == 'title': return sorted(rows,key=lambda r:(str(r.get('title','')).casefold(),r['day']))
    return sorted(rows,key=lambda r:r['day'])

def sort_readiness(rows, mode):
    if mode == 'latest': return sorted(rows,key=lambda r:r['day'],reverse=True)
    if mode == 'most_work': return sorted(rows,key=lambda r:(-(r['unassigned']+r['cleaning']),r['day']))
    return sorted(rows,key=lambda r:r['day'])

def attention_totals(issues, readiness):
    return dict(issues=len(issues),review_days=sum(bool(r['needs_review']) for r in readiness),
                unassigned=sum(r['unassigned'] for r in readiness),
                cleaning=sum(r['cleaning'] for r in readiness))

def summary_csv(hut,issues,readiness):
    rows=[('Issue',r['day'].isoformat(),r['title'],r['detail']) for r in issues]
    rows += [('Arrival readiness',r['day'].isoformat(),str(r['groups'])+' arrival groups',
              str(r['unassigned'])+' unassigned; '+str(r['cleaning'])+' unfinished cleaning tasks') for r in readiness]
    return csv_response('operations_summary_hut_%s.csv' % hut.pk,('Category','Date','Summary','Details'),rows)
