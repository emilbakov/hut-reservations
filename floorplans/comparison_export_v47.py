"""v47: manager-only CSV for the existing v46 comparison (no DB writes)."""
import csv
from django.http import HttpResponse


def safe_cell(value):
    """Prevent Excel/LibreOffice from interpreting user-controlled text as formulas."""
    text = str(value if value is not None else '')
    if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
        return "'" + text
    return text


def export_comparison_csv(hut, comparison):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = ('attachment; filename="summitdesk_hut_%s_forecast_comparison_%s.csv"' % (hut.pk, comparison['current_start'].isoformat()))
    response.write('\ufeff')  # Excel UTF-8 BOM
    writer = csv.writer(response)
    writer.writerow(['Hut', 'Previous period start', 'Previous period end', 'Selected period start', 'Selected period end', 'Metric', 'Previous 7 days', 'Selected 7 days', 'Difference', 'Change percent'])
    for metric in comparison['metrics']:
        writer.writerow([
            safe_cell(hut.name), comparison['previous_start'].isoformat(), comparison['previous_end'].isoformat(),
            comparison['current_start'].isoformat(), comparison['current_end'].isoformat(),
            safe_cell(metric['label']), metric['previous'], metric['current'], metric['delta'],
            '' if metric['change_pct'] is None else metric['change_pct'],
        ])
    return response
