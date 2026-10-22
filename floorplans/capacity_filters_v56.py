"""v56: filter the displayed capacity warnings without changing underlying totals."""

VALID_LEVELS = frozenset({'all', 'critical', 'warning', 'notice'})


def filter_capacity_watch(rows, raw_level):
    level = (raw_level or 'all').strip().lower()
    if level not in VALID_LEVELS:
        level = 'all'
    if level == 'all':
        return level, list(rows)
    return level, [row for row in rows if str(row.get('severity', '')).lower() == level]
