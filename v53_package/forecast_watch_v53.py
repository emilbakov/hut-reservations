"""SummitDesk v53: read-only, hut-scoped forecast capacity watch."""

def build_capacity_watch(rows):
    alerts = []
    for row in rows:
        usable = max(0, int(row['available_capacity']))
        confirmed = max(0, int(row['occupied']))
        pending = max(0, int(row['pending']))
        held = confirmed + pending
        free = max(0, int(row['free']))
        if held > usable:
            severity, message = 'Critical', 'Confirmed and pending beds exceed usable capacity'
            priority = 0
        elif usable == 0:
            severity, message = 'Notice', 'No usable beds available'
            priority = 2
        elif held * 100 >= usable * 90:
            severity, message = 'Warning', 'At least 90% of usable beds are reserved or held'
            priority = 1
        else:
            continue
        alerts.append({'day': row['day'], 'severity': severity, 'message': message,
                       'confirmed': confirmed, 'pending': pending, 'usable': usable,
                       'free': free, 'priority': priority})
    alerts.sort(key=lambda item: (item['priority'], item['day']))
    return alerts
