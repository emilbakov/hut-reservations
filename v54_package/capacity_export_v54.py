"""SummitDesk v54: safe, manager-scoped capacity watch CSV export."""
import csv
from django.http import HttpResponse


def _safe(value):
    text = str(value if value is not None else '')
    if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + text
    return text


def export_capacity_watch_csv(hut, rows, start_date):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="summitdesk_hut_{hut.pk}_capacity_watch_{start_date.isoformat()}.csv"'
    )
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Hut', 'Date', 'Severity', 'Warning', 'Confirmed beds', 'Pending beds', 'Usable beds', 'Free beds'])
    for item in rows:
        writer.writerow([
            _safe(hut.name), item['day'].isoformat(), _safe(item['severity']),
            _safe(item['message']), item['confirmed'], item['pending'], item['usable'], item['free'],
        ])
    return response
