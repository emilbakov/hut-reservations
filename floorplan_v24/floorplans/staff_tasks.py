"""V24: managers manage hut tasks; cleaners see and update their own tasks."""
from datetime import date
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from bookings.models import Bed, Hut, Room
from .housekeeping_models import BedHousekeeping
from .housekeeping_tasks import HousekeepingTask
from .hut_staff import HutCleaner


def access(request, hut_id):
    hut = get_object_or_404(Hut, pk=hut_id, is_active=True)
    manager = request.user.is_superuser or hut.managers.filter(pk=request.user.pk).exists()
    cleaner = HutCleaner.objects.filter(hut=hut, user=request.user).exists()
    if not manager and not cleaner:
        return hut, False, False
    return hut, manager, cleaner


@staff_member_required
@require_http_methods(['GET', 'POST'])
def staff_tasks(request, hut_id):
    hut, manager, cleaner = access(request, hut_id)
    if not (manager or cleaner):
        return HttpResponseForbidden('Not authorized for this hut')
    today = timezone.localdate()
    try:
        day = date.fromisoformat(request.GET.get('day', today.isoformat()))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid date')
    if abs((day - today).days) > 366:
        return HttpResponseBadRequest('Date outside allowed range')
    users = list(get_user_model().objects.filter(is_active=True, is_staff=True, hut_cleaner_memberships__hut=hut).distinct().order_by('username'))
    valid_users = {str(u.pk): u for u in users}
    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in ('save', 'delete', 'progress'):
            return HttpResponseBadRequest('Invalid action')
        try:
            bed_id = int(request.POST.get('bed_id', ''))
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Invalid bed')
        if not manager and action != 'progress':
            return HttpResponseForbidden('Only managers may create, reassign or delete tasks')
        with transaction.atomic():
            bed = get_object_or_404(Bed.objects.select_related('room'), pk=bed_id, room__hut=hut, room__is_active=True)
            Room.objects.select_for_update().get(pk=bed.room_id)
            task = HousekeepingTask.objects.select_for_update().filter(bed=bed, day=day).first()
            if action == 'delete':
                if task:
                    task.delete()
            elif action == 'progress':
                if not task or (not manager and task.assignee_id != request.user.pk):
                    return HttpResponseForbidden('This task is not assigned to you')
                status = request.POST.get('status')
                if status not in ('open', 'in_progress', 'done'):
                    return HttpResponseBadRequest('Invalid status')
                task.status = status
                task.updated_by = request.user
                task.completed_at = (task.completed_at or timezone.now()) if status == 'done' else None
                task.save(update_fields=['status', 'updated_by', 'completed_at', 'updated_at'])
            else:
                status = request.POST.get('status')
                priority = request.POST.get('priority')
                assignee_id = request.POST.get('assignee', '')
                if status not in ('open', 'in_progress', 'done') or priority not in ('low', 'normal', 'high'):
                    return HttpResponseBadRequest('Invalid status or priority')
                if assignee_id and assignee_id not in valid_users:
                    return HttpResponseBadRequest('Assignee must be an active cleaner of this hut')
                completed = (task.completed_at if task and task.status == 'done' else timezone.now()) if status == 'done' else None
                HousekeepingTask.objects.update_or_create(bed=bed, day=day, defaults={
                    'assignee': valid_users.get(assignee_id), 'priority': priority,
                    'status': status, 'note': request.POST.get('note', '').strip()[:240],
                    'updated_by': request.user, 'completed_at': completed,
                })
        return redirect(f'{request.path}?day={day.isoformat()}')
    beds = list(Bed.objects.filter(room__hut=hut, room__is_active=True).select_related('room').order_by('room__position', 'room_id', 'number'))
    task_qs = HousekeepingTask.objects.filter(bed__in=beds, day=day).select_related('assignee', 'updated_by')
    if not manager:
        task_qs = task_qs.filter(assignee=request.user)
    tasks = {t.bed_id: t for t in task_qs}
    if not manager:
        beds = [b for b in beds if b.pk in tasks]
    cleaning = {s.bed_id: s.state for s in BedHousekeeping.objects.filter(bed__in=beds)}
    rows = [{'bed': b, 'task': tasks.get(b.pk), 'cleaning': cleaning.get(b.pk, 'unknown')} for b in beds]
    return render(request, 'floorplans/staff_tasks.html', {
        'hut': hut, 'day': day, 'rows': rows, 'users': users, 'is_manager': manager,
        'total': len(tasks), 'open_count': sum(t.status == 'open' for t in tasks.values()),
        'progress_count': sum(t.status == 'in_progress' for t in tasks.values()),
        'done_count': sum(t.status == 'done' for t in tasks.values()),
    })


@staff_member_required
@require_http_methods(['GET', 'POST'])
def cleaner_team(request, hut_id):
    hut, manager, _ = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden('Only hut managers can manage the team')
    if request.method == 'POST':
        try:
            user_id = int(request.POST.get('user_id', ''))
        except (ValueError, TypeError):
            return HttpResponseBadRequest('Invalid user')
        user = get_object_or_404(get_user_model(), pk=user_id, is_active=True, is_staff=True)
        action = request.POST.get('action')
        if action == 'add':
            HutCleaner.objects.get_or_create(hut=hut, user=user)
        elif action == 'remove':
            HutCleaner.objects.filter(hut=hut, user=user).delete()
        else:
            return HttpResponseBadRequest('Invalid action')
        return redirect(request.path)
    members = HutCleaner.objects.filter(hut=hut).select_related('user')
    candidates = get_user_model().objects.filter(is_active=True, is_staff=True).order_by('username')
    return render(request, 'floorplans/cleaner_team.html', {'hut': hut, 'members': members, 'candidates': candidates})
