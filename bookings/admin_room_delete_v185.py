"""Explicit admin deletion of unused units; never discard operational history."""
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models.deletion import Collector, ProtectedError, RestrictedError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .models import Bed


class UnusedRoomError(Exception):
    pass


def check_unused(rooms, using):
    """Return the bed deletion collector after checking every selected room."""
    for room in rooms:
        # Refuse even cancelled/old bookings, and future model relationships.
        for relation in room._meta.related_objects:
            if relation.related_model._meta.label_lower in {
                "bookings.bed", "floorplans.roomplacement", "bookings.roomphoto"
            }:
                continue
            if relation.related_model._base_manager.using(using).filter(
                **{relation.field.name: room}
            ).exists():
                raise UnusedRoomError(
                    f"{room}: linked {relation.related_model._meta.verbose_name} records exist."
                )
    beds = Bed.objects.using(using).filter(room_id__in=[room.pk for room in rooms])
    collector = Collector(using=using)
    collector.collect(beds)
    allowed = {"bookings.bed", "floorplans.bedmarker"}
    models = {model for model, objects in collector.data.items() if objects}
    models.update(query.model for query in collector.fast_deletes if query.exists())
    if any(model._meta.label_lower not in allowed for model in models):
        raise UnusedRoomError("Beds have linked operational history. Nothing can be deleted.")
    if any(
        batch.exists() if hasattr(batch, "exists") else bool(batch)
        for batches in collector.field_updates.values() for batch in batches
    ):
        raise UnusedRoomError("Beds have linked records that would be modified. Deletion refused.")
    return collector


@admin.action(description="Delete unused rooms and their beds…", permissions=["delete"])
def delete_unused_rooms(modeladmin, request, queryset):
    if not modeladmin.has_delete_permission(request):
        raise PermissionDenied
    using = queryset.db
    rooms = list(queryset.order_by("pk"))
    if not rooms:
        return None
    for room in rooms:
        if not modeladmin.has_delete_permission(request, room):
            raise PermissionDenied
    destination = reverse("admin:bookings_room_changelist", current_app=modeladmin.admin_site.name)
    try:
        check_unused(rooms, using)
        if request.POST.get("confirm_unused_room_delete") == "yes":
            # Creation services lock these same rows. Recheck after acquiring locks.
            with transaction.atomic(using=using):
                # Admin joins the nullable hut FK; PostgreSQL cannot lock that
                # outer join. Lock only the Room rows, in the service lock order.
                locked = list(queryset.select_related(None).select_for_update().order_by("pk"))
                if [room.pk for room in locked] != [room.pk for room in rooms]:
                    raise UnusedRoomError("The room selection changed. Select the rooms again.")
                list(Bed.objects.using(using).select_for_update().filter(
                    room_id__in=[room.pk for room in locked]
                ).order_by("pk"))
                collector = check_unused(locked, using)
                modeladmin.log_deletions(request, locked)
                collector.delete()
                for room in locked:
                    room.delete(using=using)
            modeladmin.message_user(request, f"Deleted {len(rooms)} unused room(s) and their beds.", messages.SUCCESS)
            return HttpResponseRedirect(destination)
    except (UnusedRoomError, ProtectedError, RestrictedError) as exc:
        explanation = str(exc) if isinstance(exc, UnusedRoomError) else "Linked bookings, bed assignments, closures or other protected records exist."
        modeladmin.message_user(request, f"Nothing deleted. {explanation} Deactivate the room instead if it has history.", messages.ERROR)
        return HttpResponseRedirect(destination)
    request.current_app = modeladmin.admin_site.name
    return TemplateResponse(request, "admin/bookings/room/delete_unused_v185.html", {
        **modeladmin.admin_site.each_context(request),
        "title": "Delete unused rooms and beds?",
        "opts": modeladmin.model._meta,
        "rooms": rooms,
        "bed_count": Bed.objects.using(using).filter(room_id__in=[room.pk for room in rooms]).count(),
        "action_checkbox_name": ACTION_CHECKBOX_NAME,
        "cancel_url": destination,
    })
