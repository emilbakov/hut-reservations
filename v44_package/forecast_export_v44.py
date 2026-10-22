"""Read-only CSV export of the authorized hut's existing seven-day forecast."""
import csv
from django.http import HttpResponse


def export_forecast_csv(hut, forecast):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="summitdesk_hut_{hut.pk}_7_day_forecast.csv"'
    response['Cache-Control'] = 'private, no-store'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Date', 'Confirmed beds', 'Pending beds', 'Usable capacity',
                     'Free beds', 'Arrivals (bed places)', 'Departures (bed places)',
                     'Closed beds', 'Cleaning tasks', 'Over capacity'])
    for day in forecast:
        writer.writerow([
            day['day'].isoformat(), day['occupied'], day['pending'],
            day['available_capacity'], day['free'], day['arrivals'],
            day['departures'], day['closed'], day['tasks'],
            'Yes' if day.get('over_capacity') else 'No',
        ])
    return response
