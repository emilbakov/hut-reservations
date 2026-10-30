"""Whole-unit seasonal quotes and immutable reservation rate snapshots."""
from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

ZERO = Decimal('0.00')

def season(day):
    return 'summer' if 5 <= day.month <= 10 else 'winter'

def room_rates(room):
    return {name: getattr(room, name + '_price') if getattr(room, name + '_price') is not None else room.price_per_night
            for name in ('summer', 'winter')}

def snapshot(room):
    rates = room_rates(room)
    if all(value == room.price_per_night for value in rates.values()):
        return {}
    return {key: str(value) for key, value in rates.items()}

def nights(start, end):
    day = start
    while day < end:
        yield day
        day += timedelta(days=1)

def rate_on(item, day):
    if item.seasonal_rates:
        return Decimal(item.seasonal_rates[season(day)])
    return item.price_per_night

def lines(rates, start, end):
    counts = {'summer': 0, 'winter': 0}
    for day in nights(start, end):
        counts[season(day)] += 1
    return [{'season': key, 'label': _('Summer') if key == 'summer' else _('Winter'),
             'nights': counts[key], 'rate': Decimal(rates[key]),
             'total': Decimal(rates[key]) * counts[key]}
            for key in ('summer', 'winter') if counts[key]]

def attach_quote(room, start, end, item=None):
    rates = (item.seasonal_rates or dict.fromkeys(('summer', 'winter'), item.price_per_night)) if item else room_rates(room)
    room.quote_lines = lines(rates, start, end)
    room.quoted_total = sum((line['total'] for line in room.quote_lines), ZERO)
    return room.quoted_total

def validate_snapshot(value):
    if value == {}:
        return
    try:
        if not isinstance(value, dict) or set(value) != {'summer', 'winter'}:
            raise ValueError
        for rate in value.values():
            amount = Decimal(str(rate))
            if not amount.is_finite() or amount < 0 or amount > Decimal('99999.99') or amount != amount.quantize(Decimal('.01')):
                raise ValueError
    except (ValueError, TypeError, ArithmeticError):
        raise ValidationError('Invalid seasonal price snapshot.')

def validate_agreed_item(item):
    if not item.pk:
        return
    old = type(item).objects.filter(pk=item.pk).values('seasonal_rates', 'room_id', 'price_per_night').first()
    if old and old['seasonal_rates'] and (
        old['room_id'] != item.room_id or old['price_per_night'] != item.price_per_night
    ):
        raise ValidationError('This item has agreed seasonal rates. Remove and add a room allocation to quote a different room or rate; withdraw any active deposit hold first.')
