"""Scoped room details, seasonal rates and optional booking photo."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect,render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from .bed_management import allowed_rooms
from .models import Room
from .room_gallery_v188 import RoomPhotoFormSet

class RoomDetailsForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ('room_type','summer_price','winter_price','image','extras_en','extras_bg')
        widgets = {'extras_en':forms.Textarea(attrs={'rows':5}),
                   'extras_bg':forms.Textarea(attrs={'rows':5})}

@login_required(login_url='/staff/login/')
@require_http_methods(['GET','POST'])
def room_details(request,room_id):
    room=get_object_or_404(allowed_rooms(request.user),pk=room_id)
    form=RoomDetailsForm(request.POST if request.method=='POST' else None,
        request.FILES if request.method=='POST' else None,instance=room)
    has_gallery_data = request.method=='POST' and any(
        key.startswith('gallery-') for key in list(request.POST) + list(request.FILES))
    gallery = RoomPhotoFormSet(request.POST if has_gallery_data else None,
        request.FILES if has_gallery_data else None, instance=room, prefix='gallery')
    form_valid = form.is_valid() if request.method=='POST' else False
    gallery_valid = gallery.is_valid() if has_gallery_data else True
    if request.method=='POST' and form_valid and gallery_valid:
        with transaction.atomic():
            locked=get_object_or_404(allowed_rooms(request.user).select_related(None).select_for_update(),pk=room_id)
            for field in form.Meta.fields:
                Room._meta.get_field(field).save_form_data(locked,form.cleaned_data[field])
            locked.save(update_fields=list(form.Meta.fields))
            if has_gallery_data:
                gallery.instance=locked
                gallery.save()
        messages.success(request,_('Accommodation details saved.'))
        return redirect('bookings:room_details',room_id=room.pk)
    return render(request,'bookings/room_details_v184.html',{'room':room,'form':form,'gallery':gallery})
