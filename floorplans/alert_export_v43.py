"""SummitDesk v43: export already authorized, filtered alert rows to CSV."""
import csv
from django.http import HttpResponse


def _safe_cell(value):
    text = str(value if value is not None else '')
    # Avoid spreadsheet formula execution, including whitespace-prefixed payloads.
    if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + text
    return text


def export_alerts_csv(hut, filtered_rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="summitdesk_hut_{hut.pk}_alerts.csv"'
    response.write('\ufeff')  # Excel UTF-8 compatibility
    writer = csv.writer(response)
    writer.writerow(['Severity', 'Date', 'Title', 'Description'])
    for alert in filtered_rows:
        day = alert.get('day')
        writer.writerow([
            _safe_cell(alert.get('level', '')),
            day.isoformat() if hasattr(day, 'isoformat') else _safe_cell(day),
            _safe_cell(alert.get('title', '')),
            _safe_cell(alert.get('detail', '')),
        ])
    return response
