"""SummitDesk v40: manager alert prioritization; pure, read-only."""


def summarize_alerts(alerts):
    """Count by severity and sort without mutating the original alert list."""
    priority = {'urgent': 0, 'warning': 1, 'info': 2}
    ordered = sorted(alerts, key=lambda a: (priority.get(a.get('level'), 3), a.get('day')))
    counts = {level: sum(a.get('level') == level for a in alerts) for level in ('urgent', 'warning', 'info')}
    return {'counts': counts, 'total': len(alerts), 'top': ordered[:5]}
