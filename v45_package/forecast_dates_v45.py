"""Validated, bounded forecast date selection for authorized managers."""
from datetime import date, timedelta


def select_forecast_start(raw, today):
    """Allow today through 365 days ahead; invalid input falls back to today."""
    if not raw or len(raw) != 10:
        return today
    try:
        chosen = date.fromisoformat(raw)
    except (TypeError, ValueError):
        return today
    return chosen if today <= chosen <= today + timedelta(days=365) else today
