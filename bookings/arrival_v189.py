"""Editable hut arrival facts and read-only guest/email presentation."""
from urllib.parse import urlencode
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from .models import Hut
from .public_profile_v149 import localized


def arrival_information(hut):
    sections=[]
    for field,label in [('arrival_directions',_('Directions')),('parking',_('Parking')),('arrival_notes',_('Arrival notes'))]:
        text,lang=localized(hut,field)
        if text.strip():sections.append({'label':label,'text':text,'lang':lang})
    first,last=hut.check_in_from,hut.check_in_until
    if first is not None and last is not None:window=first.strftime('%H:%M')+' – '+last.strftime('%H:%M')
    elif first is not None:window=_('From %(time)s') % {'time':first.strftime('%H:%M')}
    elif last is not None:window=_('Until %(time)s') % {'time':last.strftime('%H:%M')}
    else:window=''
    checkout=hut.check_out_until.strftime('%H:%M') if hut.check_out_until is not None else ''
    return {'arrival_sections':sections,'check_in_window':window,'check_out_time':checkout,
            'arrival_available':bool(sections or window or checkout)}


def arrival_email_text(hut):
    """Bilingual plain text; existing bookings do not persist a guest language."""
    from .booking_flow_v150 import hut_information
    blocks=[]
    for language in ('en','bg'):
        with translation.override(language):
            info=hut_information(hut)
            if not (info['arrival_available'] or info['phone'] or info['email'] or info['directions']):
                continue
            lines=[_('Arrival information'),hut.name]
            if hut.location:lines.append(hut.location)
            if info['check_in_window']:lines.append(_('Check-in')+': '+info['check_in_window'])
            if info['check_out_time']:lines.append(_('Check-out by')+': '+info['check_out_time'])
            if info['check_in_window'] or info['check_out_time']:lines.append(_('Times are local to the hut.'))
            for section in info['arrival_sections']:lines.extend([section['label']+':',section['text']])
            if info['directions']:lines.append(_('Location and directions')+': '+info['directions'])
            if info['phone']:lines.append(_('Hut phone')+': '+info['phone'])
            if info['email']:lines.append(_('Hut email')+': '+info['email'])
            blocks.append('\n'.join(lines))
    return '\n\n'+'\n\n'.join(blocks)+'\n' if blocks else ''


def reservation_arrival_email(reservation):
    huts={}
    for item in reservation.items.select_related('room__hut'):
        if item.room.hut_id:huts.setdefault(item.room.hut_id,item.room.hut)
    return ''.join(arrival_email_text(hut) for hut in huts.values())


class ArrivalForm(forms.ModelForm):
    class Meta:
        model=Hut
        fields=('public_phone','public_email','directions_url','check_in_from','check_in_until','check_out_until',
                'arrival_directions_en','arrival_directions_bg','parking_en','parking_bg','arrival_notes_en','arrival_notes_bg')
        widgets={**{name:forms.TimeInput(format='%H:%M',attrs={'type':'time'}) for name in
                    ('check_in_from','check_in_until','check_out_until')},
                 **{name:forms.Textarea(attrs={'rows':3}) for name in
                    ('arrival_directions_en','arrival_directions_bg','parking_en','parking_bg','arrival_notes_en','arrival_notes_bg')}}


@login_required(login_url='/staff/login/')
@require_http_methods(['GET','POST'])
def arrival_settings(request):
    huts=Hut.objects.all() if request.user.is_superuser else Hut.objects.filter(managers=request.user)
    if not huts.exists():raise PermissionDenied
    hut=None
    if request.method=='POST':
        value=request.POST.get('hut_id','')
        if not value.isascii() or not value.isdecimal():raise PermissionDenied
        hut=get_object_or_404(huts,pk=int(value))
    elif request.GET.get('hut'):hut=get_object_or_404(huts,slug=request.GET['hut'])
    elif huts.count()==1:hut=huts.first()
    form=ArrivalForm(request.POST if request.method=='POST' else None,instance=hut) if hut else None
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            locked=get_object_or_404(huts.select_for_update(),pk=hut.pk)
            for field in form.Meta.fields:setattr(locked,field,form.cleaned_data[field])
            locked.save(update_fields=list(form.Meta.fields))
        messages.success(request,_('Arrival information saved.'))
        return redirect(reverse('bookings:arrival_settings')+'?'+urlencode({'hut':hut.slug}))
    from .booking_flow_v150 import hut_information
    return render(request,'bookings/arrival_settings_v189.html',{
        'huts':huts,'selected_hut':hut,'selected_slug':hut.slug if hut else '',
        'form':form,'hut_info':hut_information(hut) if hut else None})
