"""SummitDesk v42: keyword search within existing hut-scoped alert rows."""

MAX_QUERY_LENGTH = 100


def search_alerts(filtered, query):
    """Filter already-authorized v41 rows; never queries other huts."""
    term = (query or '').strip()[:MAX_QUERY_LENGTH]
    rows = filtered['rows']
    if term:
        needle = term.casefold()
        rows = [row for row in rows if needle in str(row.get('title', '')).casefold()
                or needle in str(row.get('detail', '')).casefold()]
    return {'query': term, 'rows': rows, 'shown': len(rows),
            'severity_total': filtered['shown'], 'total': filtered['total']}
