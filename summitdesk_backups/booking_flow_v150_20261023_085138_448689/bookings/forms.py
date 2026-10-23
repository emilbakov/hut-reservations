from datetime import timedelta

from django import forms
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class SearchForm(forms.Form):
    check_in = forms.DateField(label=_("Arrival"), widget=DateInput())
    check_out = forms.DateField(label=_("Departure"), widget=DateInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate().isoformat()
        self.fields["check_in"].widget.attrs["min"] = today
        self.fields["check_out"].widget.attrs["min"] = today

    def clean(self):
        data = super().clean()
        check_in, check_out = data.get("check_in"), data.get("check_out")
        if not check_in or not check_out:
            return data
        today = timezone.localdate()
        if check_in < today:
            self.add_error("check_in", _("Arrival cannot be in the past."))
        elif check_in > today + timedelta(days=settings.BOOKING_MAX_DAYS_AHEAD):
            self.add_error("check_in", _("That is too far ahead to book online."))
        if check_out <= check_in:
            self.add_error("check_out", _("Departure must be after arrival."))
        elif (check_out - check_in).days > settings.BOOKING_MAX_NIGHTS:
            self.add_error(
                "check_out",
                _("Online bookings are limited to %(count)s nights.") % {"count": settings.BOOKING_MAX_NIGHTS},
            )
        return data


class BookingForm(forms.Form):
    """Guest details plus one "how many beds" field per room with space."""

    name = forms.CharField(max_length=100, label=_("Name"))
    email = forms.EmailField(label=_("Email"))
    phone = forms.CharField(max_length=30, required=False, label=_("Phone"))
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label=_("Notes for the hut keeper"),
    )

    def __init__(self, *args, rooms, free, **kwargs):
        super().__init__(*args, **kwargs)
        self.rooms = rooms
        self.free = free
        for room in rooms:
            if free[room.pk] > 0:
                self.fields[self.field_name(room)] = forms.IntegerField(
                    label=room.name,
                    min_value=0,
                    max_value=free[room.pk],
                    required=False,
                    initial=0,
                    widget=forms.NumberInput(
                        attrs={"data-price": str(room.price_per_night), "class": "beds"}
                    ),
                    error_messages={
                        "max_value": _("Only %(count)s left in %(room)s.") % {"count": free[room.pk], "room": room.name},
                    },
                )

    @staticmethod
    def field_name(room):
        return f"room_{room.pk}"

    def rows(self):
        """(room, beds free, bound field or None) for the template."""
        for room in self.rooms:
            name = self.field_name(room)
            yield room, self.free[room.pk], self[name] if name in self.fields else None

    def beds_by_room(self):
        return {
            room.pk: self.cleaned_data.get(self.field_name(room)) or 0 for room in self.rooms
        }

    def clean(self):
        data = super().clean()
        if not self.errors and not any(self.beds_by_room().values()):
            raise forms.ValidationError(_("Choose at least one bed."))
        return data
