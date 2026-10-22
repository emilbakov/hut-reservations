
from collections import defaultdict

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import Hut, Room, Reservation, ReservationItem
from .services import free_beds, lock_rooms


# ----------------------------------
# HUT ADMIN
# ----------------------------------

def is_hut_manager(request):
    user = request.user

    if not user.is_authenticated:
        return False

    return Hut.objects.filter(managers=user).exists()


class ProtectManagerAdmin:
    """Managers use the read-only dashboard, not unrestricted Django Admin."""
    def has_module_permission(self, request):
        return not is_hut_manager(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return not is_hut_manager(request) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return not is_hut_manager(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return not is_hut_manager(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not is_hut_manager(request) and super().has_delete_permission(request, obj)


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    fields = [
        "name",
        "description",
        "capacity",
        "price_per_night",
        "is_active",
        "position",
    ]
    show_change_link = True


@admin.register(Hut)
class HutAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    list_display = [
        "name",
        "location",
        "room_count",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "location"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RoomInline]
    filter_horizontal = ["managers"]

    @admin.display(description="Rooms")
    def room_count(self, obj):
        return obj.rooms.count()


# ----------------------------------
# ROOM ADMIN
# ----------------------------------

@admin.register(Room)
class RoomAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    list_display = [
        "name",
        "hut",
        "capacity",
        "price_per_night",
        "is_active",
        "position",
    ]

    list_filter = [
        "hut",
        "is_active",
    ]

    list_editable = [
        "capacity",
        "price_per_night",
        "is_active",
        "position",
    ]

    search_fields = [
        "name",
        "hut__name",
    ]

    list_select_related = ["hut"]


# ----------------------------------
# RESERVATION VALIDATION
# ----------------------------------

class ItemFormSet(BaseInlineFormSet):
    """
    Prevent overbooking when reservations
    are edited manually in Django Admin.
    """

    def clean(self):
        super().clean()

        reservation = self.instance

        if (
            any(self.errors)
            or not (reservation.check_in and reservation.check_out)
            or reservation.check_out <= reservation.check_in
            or reservation.status == Reservation.Status.CANCELLED
        ):
            return

        wanted = defaultdict(int)
        selected_huts = set()

        for form in self.forms:
            data = getattr(form, "cleaned_data", None)

            if (
                data
                and data.get("room")
                and not data.get("DELETE")
            ):
                room = data["room"]
                wanted[room.pk] += data["beds"]

                if room.hut_id:
                    selected_huts.add(room.hut_id)

        # A reservation must not mix rooms from different huts.
        if len(selected_huts) > 1:
            raise ValidationError(
                "All rooms in one reservation must belong "
                "to the same hut."
            )

        rooms = lock_rooms(wanted)

        free = free_beds(
            rooms,
            reservation.check_in,
            reservation.check_out,
            exclude=reservation if reservation.pk else None,
        )

        problems = [
            (
                f"{room}: {wanted[room.pk]} beds requested, "
                f"only {free[room.pk]} free on these dates."
            )
            for room in rooms
            if wanted[room.pk] > free[room.pk]
        ]

        if problems:
            raise ValidationError(problems)


class ItemInline(admin.TabularInline):
    model = ReservationItem
    formset = ItemFormSet
    extra = 1


# ----------------------------------
# RESERVATION ADMIN
# ----------------------------------

class HutReservationFilter(admin.SimpleListFilter):
    title = "hut"
    parameter_name = "hut"

    def lookups(self, request, model_admin):
        return [
            (str(hut.pk), hut.name)
            for hut in Hut.objects.all()
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                items__room__hut_id=self.value()
            ).distinct()

        return queryset


@admin.register(Reservation)
class ReservationAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    list_display = [
        "name",
        "hut_name",
        "check_in",
        "check_out",
        "beds",
        "status",
        "email",
        "phone",
        "created",
    ]

    list_filter = [
        HutReservationFilter,
        "status",
        "check_in",
        "created",
    ]

    list_per_page = 30

    search_fields = [
        "name",
        "email",
        "phone",
        "code",
        "items__room__hut__name",
    ]

    date_hierarchy = "check_in"

    readonly_fields = [
        "code",
        "created",
    ]

    inlines = [ItemInline]

    actions = ["cancel"]

    change_list_template = (
        "admin/bookings/reservation/change_list.html"
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("items__room__hut")
            .distinct()
        )

    @admin.display(description="Hut")
    def hut_name(self, obj):
        huts = {
            item.room.hut.name
            for item in obj.items.all()
            if item.room.hut_id
        }

        return ", ".join(sorted(huts)) if huts else "—"

    @admin.display(description="Beds")
    def beds(self, obj):
        return obj.total_beds

    @admin.action(description="Cancel selected reservations")
    def cancel(self, request, queryset):
        updated = queryset.update(
            status=Reservation.Status.CANCELLED
        )

        self.message_user(
            request,
            f"{updated} reservation(s) cancelled.",
        )
