"""v50: summarize existing hut-scoped, read-only forecast rows."""

def summarize_forecast(rows):
    rows = list(rows)
    return {
        'confirmed': sum(int(row['occupied']) for row in rows),
        'pending': sum(int(row['pending']) for row in rows),
        'free': sum(int(row['free']) for row in rows),
        'warnings': sum(bool(row['over_capacity']) for row in rows),
    }
