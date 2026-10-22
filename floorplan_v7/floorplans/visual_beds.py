"""V7 visual bed page. Existing V6 endpoints enforce assignment rules."""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from .bed_management import permitted_hut

@staff_member_required
@require_GET
def visual_beds(request, hut_id):
    hut = permitted_hut(request, hut_id)
    return render(request, 'floorplans/visual_beds.html', {
        'hut': hut, 'today_iso': timezone.localdate().isoformat(),
    })
