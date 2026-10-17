from collections import defaultdict

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import Reservation, ReservationItem, Room
from .services import free_beds, lock_rooms


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["name", "capacity", "price_per_night", "is_active", "position"]
    list_editable = ["capacity", "price_per_night", "is_active", "position"]


class ItemFormSet(BaseInlineFormSet):
    """Stops the hut keeper from overbooking a room by hand in the admin."""

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
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if data and data.get("room") and not data.get("DELETE"):
                wanted[data["room"].pk] += data["beds"]

        rooms = lock_rooms(wanted)  # the admin view already runs in a transaction
        free = free_beds(
            rooms,
            reservation.check_in,
            reservation.check_out,
            exclude=reservation if reservation.pk else None,
        )
        problems = [
            f"{room}: {wanted[room.pk]} beds requested, only {free[room.pk]} free on these dates."
            for room in rooms
            if wanted[room.pk] > free[room.pk]
        ]
        if problems:
            raise ValidationError(problems)


class ItemInline(admin.TabularInline):
    model = ReservationItem
    formset = ItemFormSet
    extra = 1


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ["name", "check_in", "check_out", "beds", "status", "email", "phone", "created"]
    list_filter = ["status", "check_in", "created"]
    list_per_page = 30
    search_fields = ["name", "email", "phone", "code"]
    date_hierarchy = "check_in"
    readonly_fields = ["code", "created"]
    inlines = [ItemInline]
    actions = ["cancel"]
    change_list_template = "admin/bookings/reservation/change_list.html"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items")

    @admin.display(description="Beds")
    def beds(self, obj):
        return obj.total_beds

    @admin.action(description="Cancel selected reservations")
    def cancel(self, request, queryset):
        updated = queryset.update(status=Reservation.Status.CANCELLED)
        self.message_user(request, f"{updated} reservation(s) cancelled.")
