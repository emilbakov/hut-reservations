"""V23 housekeeping task board. Tasks are separate from cleaning readiness."""
from datetime import date, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from bookings.models import Bed, Room
from .bed_management import permitted_hut
from .housekeeping_models import BedHousekeeping
from .housekeeping_tasks import HousekeepingTask

@staff_member_required
@require_http_methods(['GET','POST'])
def staff_tasks(request, hut_id):
    hut = permitted_hut(request, hut_id)
    today = timezone.localdate()
    try:
        day = date.fromisoformat(request.GET.get('day', today.isoformat()))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid date')
    if abs((day - today).days) > 366:
        return HttpResponseBadRequest('Date outside allowed range')
    users = list(get_user_model().objects.filter(is_active=True, is_staff=True).order_by('username'))
    valid_users = {str(u.pk):u for u in users}
    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in ('save','delete'):
            return HttpResponseBadRequest('Invalid action')
        try:
            bed_id = int(request.POST.get('bed_id',''))
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Invalid bed')
        with transaction.atomic():
            bed = get_object_or_404(Bed.objects.select_related('room'), pk=bed_id, room__hut=hut, room__is_active=True)
            Room.objects.select_for_update().get(pk=bed.room_id)
            if action == 'delete':
                HousekeepingTask.objects.filter(bed=bed, day=day).delete()
            else:
                status = request.POST.get('status')
                priority = request.POST.get('priority')
                assignee_id = request.POST.get('assignee','')
                if status not in ('open','in_progress','done') or priority not in ('low','normal','high'):
                    return HttpResponseBadRequest('Invalid status or priority')
                if assignee_id and assignee_id not in valid_users:
                    return HttpResponseBadRequest('Invalid assignee')
                note = request.POST.get('note','').strip()[:240]
                old = HousekeepingTask.objects.filter(bed=bed,day=day).first()
                completed = (old.completed_at if old and old.status=='done' else timezone.now()) if status=='done' else None
                HousekeepingTask.objects.update_or_create(bed=bed, day=day, defaults={
                    'assignee': valid_users.get(assignee_id), 'priority':priority,
                    'status':status, 'note':note, 'updated_by':request.user,
                    'completed_at':completed,
                })
        return redirect(f'{request.path}?day={day.isoformat()}')
    beds = list(Bed.objects.filter(room__hut=hut,room__is_active=True).select_related('room').order_by('room__position','room_id','number'))
    tasks = {t.bed_id:t for t in HousekeepingTask.objects.filter(bed__in=beds,day=day).select_related('assignee','updated_by')}
    cleaning = {s.bed_id:s.state for s in BedHousekeeping.objects.filter(bed__in=beds)}
    rows = [{'bed':b,'task':tasks.get(b.pk),'cleaning':cleaning.get(b.pk,'unknown')} for b in beds]
    return render(request,'floorplans/staff_tasks.html',{
        'hut':hut,'day':day,'rows':rows,'users':users,
        'total':len(tasks),'open_count':sum(t.status=='open' for t in tasks.values()),
        'progress_count':sum(t.status=='in_progress' for t in tasks.values()),
        'done_count':sum(t.status=='done' for t in tasks.values()),
    })
