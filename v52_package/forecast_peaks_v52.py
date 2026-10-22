"""Read-only extrema from the already hut-scoped seven-day forecast."""

def summarize_peaks(rows):
    rows = list(rows)
    if not rows:
        return {'peak': None, 'quiet': None, 'most_free': None}
    # Preserve first date on ties; bed-place totals, not guest counts.
    return {
        'peak': max(rows, key=lambda r: int(r['occupied']) + int(r['pending'])),
        'quiet': min(rows, key=lambda r: int(r['occupied']) + int(r['pending'])),
        'most_free': max(rows, key=lambda r: int(r['free'])),
    }
