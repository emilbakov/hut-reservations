"""SummitDesk v55: summarize the already calculated v53 capacity warnings."""

def summarize_capacity_watch(rows):
    counts = {'critical': 0, 'warning': 0, 'notice': 0, 'total': 0}
    dates = set()
    for item in rows:
        severity = str(item.get('severity', '')).lower()
        if severity in counts and severity != 'total':
            counts[severity] += 1
        dates.add(item['day'])
    counts['total'] = len(dates)
    return counts
