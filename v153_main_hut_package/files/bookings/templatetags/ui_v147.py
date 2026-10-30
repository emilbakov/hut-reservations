"""Localized quantity labels. Machine-readable values never use these filters."""
from django import template
from django.utils.translation import ngettext

register = template.Library()


def quantity(value, singular, plural):
    try:
        count = int(value)
    except (ValueError, TypeError):
        count = 0
    return ngettext(singular, plural, count) % {'count': count}


@register.filter
def bed_count(value):
    return quantity(value, '%(count)s bed', '%(count)s beds')


@register.filter
def night_count(value):
    return quantity(value, '%(count)s night', '%(count)s nights')


@register.filter
def guest_count(value):
    return quantity(value, '%(count)s guest', '%(count)s guests')


@register.filter
def room_count(value):
    return quantity(value, '%(count)s room', '%(count)s rooms')


@register.filter
def hut_count(value):
    return quantity(value, '%(count)s hut', '%(count)s huts')
