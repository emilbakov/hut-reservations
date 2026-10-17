"""Staff-only calendar actions. Capacity checks delegated to booking services."""
from datetime import date
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .models import Reservation, Room
from .services import NotAvailable, create_reservation, free_beds, modify_reservation
from .views import manageable_reservations, permitted_hut_selection

class CalendarBookingForm(forms.Form):
    check_in = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    check_out = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    room = forms.ModelChoiceField(queryset=Room.objects.none())
    beds = forms.IntegerField(min_value=1)
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea)

    def __init__(self, *args, rooms, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = rooms

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('check_in'), cleaned.get('check_out')
        if start and end and end <= start:
            self.add_error('check_out', 'Departure must be after arrival.')
        return cleaned


def _scope(request):
    try:
        huts, selected, slug = permitted_hut_selection(request)
        return huts, selected, slug
    except PermissionDenied:
        raise Http404 from None


@staff_member_required
@require_http_methods(['GET', 'POST'])
def calendar_create(request):
    huts, selected, slug = _scope(request)
    rooms = Room.objects.filter(hut__in=huts, is_active=True).select_related('hut').order_by('hut__name', 'position', 'pk')
    if selected:
        rooms = rooms.filter(hut=selected)
    initial = {k: request.GET[k] for k in ('check_in', 'check_out', 'room') if k in request.GET}
    form = CalendarBookingForm(request.POST if request.method == 'POST' else None, rooms=rooms, initial=initial)
    available = None
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        room = data['room']
        try:
            reservation = create_reservation(
                check_in=data['check_in'], check_out=data['check_out'],
                beds_by_room={room.pk: data['beds']},
                name=data['name'], email=data['email'], phone=data['phone'], notes=data['notes'],
            )
        except (ValidationError, NotAvailable, ValueError) as exc:
            form.add_error(None, 'Reservation could not be created: ' + str(exc))
        else:
            messages.success(request, 'Reservation created. Review payment and confirmation separately.')
            return redirect('bookings:calendar_edit', code=reservation.code)
    if form.is_valid() and request.method == 'POST':
        data = form.cleaned_data
        available = free_beds([data['room']], data['check_in'], data['check_out']).get(data['room'].pk)
    return render(request, 'bookings/calendar_booking_form.html', {
        'form': form, 'mode': 'create', 'available': available,
        'huts': huts, 'selected_hut': selected, 'selected_slug': slug,
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def calendar_edit(request, code):
    huts, selected, slug = _scope(request)
    allowed = manageable_reservations(request.user)
    reservation = get_object_or_404(allowed.prefetch_related('items__room'), code=code)
    items = list(reservation.items.all())
    hut_ids = {item.room.hut_id for item in items}
    if len(hut_ids) != 1 or None in hut_ids or (selected and selected.pk not in hut_ids):
        raise Http404
    # Edit only single-room reservations. Multi-room edits remain in existing management UI.
    if len(items) != 1:
        messages.info(request, 'Multi-room bookings must be managed using the existing reservation tools.')
        return redirect('bookings:manager_reservations')
    item = items[0]
    rooms = Room.objects.filter(hut_id=item.room.hut_id, is_active=True).select_related('hut')
    initial = dict(check_in=reservation.check_in, check_out=reservation.check_out,
                   room=item.room_id, beds=item.beds, name=reservation.name,
                   email=reservation.email, phone=reservation.phone, notes=reservation.notes)
    payload = request.POST.copy() if request.method == 'POST' else None
    if payload is not None:
        for key in ('name', 'email', 'phone', 'notes'):
            payload[key] = initial[key]
    form = CalendarBookingForm(payload, rooms=rooms, initial=initial)
    available = None
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        if reservation.status not in Reservation.HOLDING:
            form.add_error(None, 'Cancelled reservations cannot be modified.')
        else:
            try:
                modify_reservation(code=code, check_in=data['check_in'],
                                   check_out=data['check_out'], beds_by_room={data['room'].pk: data['beds']})
            except (ValidationError, NotAvailable, ValueError) as exc:
                form.add_error(None, 'Reservation could not be updated: ' + str(exc))
            else:
                messages.success(request, 'Dates and beds updated. Guest contact details were not changed.')
                return redirect('bookings:calendar_edit', code=code)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        available = free_beds([data['room']], data['check_in'], data['check_out'], exclude=reservation).get(data['room'].pk)
    return render(request, 'bookings/calendar_booking_form.html', {
        'form': form, 'mode': 'edit', 'reservation': reservation, 'available': available,
        'huts': huts, 'selected_hut': selected, 'selected_slug': slug,
    })
