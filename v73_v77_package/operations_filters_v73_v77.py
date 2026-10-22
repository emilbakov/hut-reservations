"""v73-v77: pure, read-only filtering and action summaries."""
from collections import Counter
from datetime import date

SORTS = ('priority', 'date')

def select_actions(actions, *, query='', action_date='', sort='priority'):
    query = (query or '').strip()[:100].casefold()
    try:
        chosen_date = date.fromisoformat(action_date) if action_date else None
    except (ValueError, TypeError):
        chosen_date = None
    result = [a for a in actions if
              (not query or query in ' '.join(str(a.get(k, '')) for k in ('label', 'detail', 'day')).casefold())
              and (chosen_date is None or a['day'] == chosen_date)]
    if sort == 'date':
        result.sort(key=lambda a:(a['day'], a['priority'], a['label'], a['detail']))
    else:
        result.sort(key=lambda a:(a['priority'], a['day'], a['label'], a['detail']))
    return result

def summarize_actions(actions):
    counts = Counter(a['priority'] for a in actions)
    return {'conflicts': counts[0], 'assignments': counts[1],
            'cleaning': counts[2], 'total': len(actions)}
