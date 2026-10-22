"""Presentation-only weekly timeline layout. Does not change reservations."""
from datetime import timedelta


def build_bars(items, start, end):
    """Place overlapping reservation items on separate tracks for a 7-night window."""
    bars = []
    for item in sorted(items, key=lambda i: (i.reservation.check_in, i.reservation.check_out, i.pk)):
        booking = item.reservation
        left = max(start, booking.check_in)
        right = min(end, booking.check_out)
        if right <= left:
            continue
        first = (left - start).days
        span = (right - left).days
        used = {b['track'] - 1 for b in bars if first < b['end_offset'] and first + span > b['start_offset']}
        track = next(i for i in range(len(bars) + 1) if i not in used)
        bars.append({
            'code': booking.code, 'guest': booking.name, 'beds': item.beds,
            'status': booking.status, 'check_in': booking.check_in,
            'check_out': booking.check_out, 'first': first + 1,
            'span': span, 'track': track + 1,
            'start_offset': first, 'end_offset': first + span,
        })
    return bars
