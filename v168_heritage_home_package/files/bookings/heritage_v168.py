"""Studenets' owner-supplied history and photographs, separate from booking."""
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext as _

from .booking_flow_v150 import hut_information
from .models import Room
from .public_profile_v149 import public_context


def heritage_home(request, hut):
    public = public_context(request)['PUBLIC149'].copy()
    public.update({
        'description': _('Discover %(hut)s, a historic mountain hut at the heart of the resort. Explore its story in photographs, then plan your stay.') % {'hut': hut.name},
        'social_image': request.build_absolute_uri(static('bookings/heritage-v168/studenets-social.jpg')),
        'social_width': 1280, 'social_height': 714,
        'social_alt': _('%(hut)s surrounded by snow-covered forest.') % {'hut': hut.name},
        'title': _('%(hut)s · At the heart of the mountain') % {'hut': hut.name},
    })
    return render(request, 'bookings/heritage_home_v168.html', {
        'hut': hut, 'hut_info': hut_information(hut), 'homepage': True,
        'public_rooms': Room.objects.filter(hut=hut, is_active=True).order_by('position', 'name'),
        'heritage_booking_url': reverse('bookings:book'), 'PUBLIC149': public,
    })
