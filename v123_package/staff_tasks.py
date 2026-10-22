"""V24: managers manage hut tasks; cleaners see and update their own tasks."""
from datetime import date
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from bookings.models import Bed, Hut, Room
from .housekeeping_models import BedHousekeeping
from .housekeeping_tasks import HousekeepingTask
from .hut_staff import HutCleaner, OfflineCleaner


def access(request, hut_id):
    hut = get_object_or_404(Hut, pk=hut_id, is_active=True)
    manager = request.user.is_superuser or hut.managers.filter(pk=request.user.pk).exists()
    cleaner = HutCleaner.objects.filter(hut=hut, user=request.user).exists()
    if not manager and not cleaner:
        return hut, False, False
    return hut, manager, cleaner


@login_required
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
    users = list(get_user_model().objects.filter(is_active=True, hut_cleaner_memberships__hut=hut).distinct().order_by('username'))
    valid_users = {str(u.pk): u for u in users}
    offline_cleaners = list(OfflineCleaner.objects.filter(hut=hut).order_by('name', 'pk')) if manager else []
    valid_offline = {str(person.pk): person for person in offline_cleaners}
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
                selection = request.POST.get('assignee', '').strip()
                if status not in ('open', 'in_progress', 'done') or priority not in ('low', 'normal', 'high'):
                    return HttpResponseBadRequest('Invalid status or priority')
                assigned_user = None
                assigned_offline = None
                if selection:
                    kind, sep, identifier = selection.partition(':')
                    if not sep:  # Existing task forms posted numeric user IDs.
                        kind, identifier = 'user', kind
                    if kind == 'user' and identifier in valid_users:
                        assigned_user = valid_users[identifier]
                    elif kind == 'offline' and identifier in valid_offline:
                        assigned_offline = valid_offline[identifier]
                    else:
                        return HttpResponseBadRequest('Assignee must belong to this hut')
                completed = (task.completed_at if task and task.status == 'done' else timezone.now()) if status == 'done' else None
                HousekeepingTask.objects.update_or_create(bed=bed, day=day, defaults={
                    'assignee': assigned_user, 'offline_assignee': assigned_offline, 'priority': priority,
                    'status': status, 'note': request.POST.get('note', '').strip()[:240],
                    'updated_by': request.user, 'completed_at': completed,
                })
        return redirect(f'{request.path}?day={day.isoformat()}')
    beds = list(Bed.objects.filter(room__hut=hut, room__is_active=True).select_related('room').order_by('room__position', 'room_id', 'number'))
    task_qs = HousekeepingTask.objects.filter(bed__in=beds, day=day).select_related('assignee', 'offline_assignee', 'updated_by')
    if not manager:
        task_qs = task_qs.filter(assignee=request.user)
    tasks = {t.bed_id: t for t in task_qs}
    if not manager:
        beds = [b for b in beds if b.pk in tasks]
    cleaning = {s.bed_id: s.state for s in BedHousekeeping.objects.filter(bed__in=beds)}
    rows = [{'bed': b, 'task': tasks.get(b.pk), 'cleaning': cleaning.get(b.pk, 'unknown')} for b in beds]
    return render(request, 'floorplans/staff_tasks.html' if manager else 'floorplans/cleaner_portal.html', {
        'hut': hut, 'day': day, 'rows': rows, 'users': users,
        'offline_cleaners': offline_cleaners, 'is_manager': manager,
        'total': len(tasks), 'open_count': sum(t.status == 'open' for t in tasks.values()),
        'progress_count': sum(t.status == 'in_progress' for t in tasks.values()),
        'done_count': sum(t.status == 'done' for t in tasks.values()),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def cleaner_team(request, hut_id):
    hut, manager, _ = access(request, hut_id)
    if not manager:
        return HttpResponseForbidden('Only hut managers can manage the team')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'add_offline':
            name = ' '.join(request.POST.get('name', '').split())
            if not name or len(name) > 100:
                messages.error(request, 'Enter a cleaner name (up to 100 characters).')
            else:
                # Lock the hut so simultaneous additions cannot create
                # duplicate names with different capitalization.
                with transaction.atomic():
                    Hut.objects.select_for_update().get(pk=hut.pk)
                    duplicate = any(
                        existing.name.casefold() == name.casefold()
                        for existing in OfflineCleaner.objects.filter(hut=hut).only('name')
                    )
                    if duplicate:
                        messages.warning(request, 'This cleaner is already on the team.')
                    else:
                        OfflineCleaner.objects.create(hut=hut, name=name)
                        messages.success(request, f'{name} added without a login account.')
        elif action in ('add', 'remove', 'remove_offline'):
            key = 'offline_id' if action == 'remove_offline' else 'user_id'
            try:
                identifier = int(request.POST.get(key, ''))
                if identifier < 1:
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, 'Choose a valid cleaner.')
                return redirect(request.path)

            if action == 'add':
                # An existing user must be active and not a superuser.
                user = get_object_or_404(get_user_model(), pk=identifier, is_active=True, is_superuser=False)
                _, created = HutCleaner.objects.get_or_create(hut=hut, user=user)
                if created:
                    messages.success(request, f'{user.get_username()} added to the team.')
                else:
                    messages.info(request, 'This account is already on the team.')
            elif action == 'remove':
                member = get_object_or_404(HutCleaner, hut=hut, user_id=identifier)
                with transaction.atomic():
                    HousekeepingTask.objects.filter(bed__room__hut=hut, assignee_id=identifier).update(assignee=None)
                    member.delete()
                messages.success(request, 'Cleaner removed. Their tasks are now unassigned.')
            else:
                person = get_object_or_404(OfflineCleaner, pk=identifier, hut=hut)
                person.delete()  # SET_NULL clears offline task assignments.
                messages.success(request, 'Name-only cleaner removed. Their tasks are now unassigned.')
        else:
            return HttpResponseBadRequest('Invalid action')
        return redirect(request.path)

    members = HutCleaner.objects.filter(hut=hut).select_related('user').order_by('user__username')
    offline_cleaners = OfflineCleaner.objects.filter(hut=hut).order_by('name', 'pk')
    candidates = get_user_model().objects.filter(
        is_active=True, is_superuser=False
    ).exclude(hut_cleaner_memberships__hut=hut).exclude(managed_huts=hut).order_by('username')
    return render(request, 'floorplans/cleaner_team.html', {
        'hut': hut, 'members': members, 'offline_cleaners': offline_cleaners,
        'candidates': candidates,
    })
