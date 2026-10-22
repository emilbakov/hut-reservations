"""Read-only utilization summary of the existing v45 hut-scoped forecast."""
from decimal import Decimal, ROUND_HALF_UP


def summarize_utilization(rows):
    rows = list(rows)
    capacity = sum(max(0, int(row['available_capacity'])) for row in rows)
    confirmed = sum(max(0, int(row['occupied'])) for row in rows)
    pending = sum(max(0, int(row['pending'])) for row in rows)

    def percent(numerator):
        if not capacity:
            return None
        return int((Decimal(numerator) * 100 / Decimal(capacity)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    return {
        'capacity': capacity,
        'confirmed': confirmed,
        'pending': pending,
        'confirmed_pct': percent(confirmed),
        'held_pct': percent(confirmed + pending),
        'days_without_capacity': sum(int(row['available_capacity']) <= 0 for row in rows),
    }
