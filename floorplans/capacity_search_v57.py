"""SummitDesk v57: keyword search of already hut-scoped, severity-filtered warnings."""

def search_capacity_watch(rows, raw_query):
    query = str(raw_query or '').strip()[:100]
    if not query:
        return '', list(rows)
    needle = query.casefold()
    filtered = []
    for row in rows:
        day = row.get('day')
        date_str = day.isoformat() if hasattr(day, 'isoformat') else str(day or '')
        haystack = ' '.join((date_str, str(row.get('severity', '')), str(row.get('message', '')))).casefold()
        if needle in haystack:
            filtered.append(row)
    return query, filtered
