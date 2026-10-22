"""Property-scoped quick stay creation. Existing booking service enforces capacity."""
from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from bookings.models import Reservation, Room
from bookings.services import NotAvailable, create_reservation
from .bed_management import permitted_hut
from .property_calendar_v138 import render_property_month


class QuickStayForm(forms.Form):
    room = forms.IntegerField(min_value=1)
    check_in = forms.DateField()
    check_out = forms.DateField()
    beds = forms.IntegerField(min_value=1)
    name = forms.CharField(max_length=100, strip=True)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=30, required=False)
    notes = forms.CharField(required=False, max_length=2000)

    def clean(self):
        data = super().clean()
        if data.get('check_in') and data.get('check_out') and data['check_out'] <= data['check_in']:
            self.add_error('check_out', 'Departure must be after arrival.')
        return data


@staff_member_required
@require_POST
def quickstay_create(request, hut_id):
    # Exactly the same property authorization as the existing calendar.
    hut = permitted_hut(request, hut_id)
    form = QuickStayForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        room = Room.objects.filter(pk=data['room'], hut=hut, is_active=True).first()
        if room is None:
            raise Http404('Room is not available for this property.')
        if data['beds'] > room.capacity:
            form.add_error('beds', 'Requested guests exceed this room’s capacity.')
        else:
            try:
                reservation = create_reservation(
                    check_in=data['check_in'], check_out=data['check_out'],
                    beds_by_room={room.pk: data['beds']},
                    status=Reservation.Status.CONFIRMED,
                    name=data['name'], email=data['email'], phone=data['phone'], notes=data['notes'],
                )
            except (NotAvailable, ValidationError, ValueError):
                form.add_error(None, 'The room is no longer available for the full stay, or the dates are invalid. Please choose different dates.')
            else:
                messages.success(request, 'Reservation created: ' + reservation.code)
                # Redirect to the existing property-scoped reservation detail.
                return redirect('floorplans:staff_reservation', hut_id=hut.pk, code=reservation.code)
    # Keep entered dates and guest name visible after validation errors.
    # The render helper already enforces guest visibility for this hut.
    try:
        arrival = date.fromisoformat(request.POST.get('check_in', ''))
    except ValueError:
        arrival = None
    response = render_property_month(request, hut, quickstay_form=form,
                                     quickstay_initial=request.POST,
                                     quickstay_arrival=arrival)
    response.status_code = 400
    return response
