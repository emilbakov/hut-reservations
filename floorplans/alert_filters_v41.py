"""SummitDesk v41: safe, read-only filters for hut-scoped operations alerts."""

LEVELS = ('all', 'urgent', 'warning', 'info')


def filter_alerts(alerts, level):
    """Return selected alerts and metadata; invalid levels fall back to all."""
    selected = level if level in LEVELS else 'all'
    rows = list(alerts) if selected == 'all' else [a for a in alerts if a.get('level') == selected]
    return {'selected': selected, 'rows': rows, 'shown': len(rows), 'total': len(alerts)}
