"""SummitDesk v46: compare two seven-night forecast windows (read-only)."""
from datetime import timedelta
from .staff_forecast_v38 import build_forecast

METRICS = (
    ('occupied', 'Confirmed bed-nights'),
    ('pending', 'Pending bed-nights'),
    ('free', 'Free bed-nights'),
    ('arrivals', 'Arriving bed places'),
    ('departures', 'Departing bed places'),
    ('closed', 'Closed bed-nights'),
    ('tasks', 'Scheduled cleaning tasks'),
)

def compare_forecast(hut, start, current_rows=None):
    """Compare chosen 7 days with immediately preceding 7 days.

    Snapshot estimates use today's room capacities, statuses and task data,
    not historical snapshots. Bed-night values sum daily bed places.
    """
    previous_start = start - timedelta(days=7)
    previous_rows = build_forecast(hut, previous_start)
    current_rows = current_rows if current_rows is not None else build_forecast(hut, start)
    metrics = []
    for key, label in METRICS:
        current = sum(int(day[key]) for day in current_rows)
        previous = sum(int(day[key]) for day in previous_rows)
        delta = current - previous
        metrics.append({
            'key': key, 'label': label, 'current': current,
            'previous': previous, 'delta': delta,
            'change_pct': (round(100 * delta / previous, 1) if previous else None),
        })
    return {
        'current_start': start,
        'current_end': start + timedelta(days=6),
        'previous_start': previous_start,
        'previous_end': start - timedelta(days=1),
        'metrics': metrics,
    }
