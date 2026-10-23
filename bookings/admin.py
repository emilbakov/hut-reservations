
from collections import defaultdict

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.urls import path, reverse
from django.shortcuts import redirect
from django.utils.html import format_html

from .models import (
    Hut, Room, Reservation, ReservationItem, HutDepositPolicy, PaymentTransaction, DepositEntry, CancellationSettlement,
)
from .deposits import deposit_summary
from .admin_cancellation_v167 import cancellation_view
from .services import free_beds, lock_rooms
from .models import PublicWebsiteSettings


@admin.register(PublicWebsiteSettings)
class PublicWebsiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Brand and contact", {"fields": ("brand_name", "operator_name", "contact_phone", "contact_email", "privacy_email", "address_en", "address_bg", "map_url")}),
        ("Homepage photo (optional)", {"fields": ("hero_image", "hero_alt_en", "hero_alt_bg")}),
        ("Privacy notice — publish reviewed wording only", {"fields": ("privacy_en", "privacy_bg", "privacy_published")}),
        ("Cancellation policy — publish reviewed wording only", {"fields": ("cancellation_en", "cancellation_bg", "cancellation_published")}),
    )

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request) and not PublicWebsiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ----------------------------------
# HUT ADMIN
# ----------------------------------

def is_hut_manager(request):
    user = request.user

    if not user.is_authenticated or user.is_superuser:
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


class HutDepositPolicyInline(admin.StackedInline):
    """Edit the hut's deposit settings directly from its admin page."""
    model = HutDepositPolicy
    extra = 1
    max_num = 1
    can_delete = False
    fields = (
        "percentage", "due_days", "reminders_enabled", "grace_days",
        "auto_cancel_enabled",
    )
    verbose_name = "Deposit policy"
    verbose_name_plural = "Deposit policy (optional — defaults apply if blank)"


@admin.register(HutDepositPolicy)
class HutDepositPolicyAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    """Deposit rules can also be managed centrally in Django admin."""
    list_display = (
        "hut", "percentage", "due_days", "reminders_enabled",
        "grace_days", "auto_cancel_enabled",
    )
    list_select_related = ("hut",)
    list_filter = ("reminders_enabled", "auto_cancel_enabled")
    search_fields = ("hut__name",)
    fields = (
        "hut", "percentage", "due_days", "reminders_enabled",
        "grace_days", "auto_cancel_enabled",
    )


@admin.register(Hut)
class HutAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "location", "image", "is_active", "managers")}),
        ("Public booking information", {
            "description": "Enter the actual hut contact, directions, response expectations and payment terms. Blank fields use neutral wording; no response deadline or payment method is invented.",
            "fields": ("public_phone", "public_email", "directions_url", "reply_time_en", "reply_time_bg", "payment_instructions_en", "payment_instructions_bg"),
        }),
    )
    list_display = [
        "name",
        "location",
        "room_count",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["name", "location"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RoomInline, HutDepositPolicyInline]
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


class DepositPaymentsInline(admin.TabularInline):
    """Display payment history without bypassing the validated staff ledger."""
    model = PaymentTransaction
    extra = 0
    can_delete = False
    fields = ("created", "kind", "method", "amount", "note", "recorded_by")
    readonly_fields = fields
    verbose_name_plural = "Payments and deposits (read-only audit history)"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DepositEntry)
class DepositEntryAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    """Separate, read-only list of actual deposit transactions.

    Deposits remain in PaymentTransaction; no duplicate balances or records.
    Record new deposits through the existing staff payment workflow.
    """
    list_display = (
        "created", "amount", "reservation_link", "guest_name",
        "hut_names", "method", "recorded_by", "note",
    )
    list_filter = ("method", "created")
    search_fields = (
        "reservation__code", "reservation__name", "reservation__email", "note",
    )
    readonly_fields = (
        "reservation", "kind", "method", "amount", "note", "created", "recorded_by",
    )
    fields = readonly_fields
    list_per_page = 50
    date_hierarchy = "created"
    ordering = ("-created", "-pk")

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .filter(kind=PaymentTransaction.Kind.DEPOSIT)
            .select_related("reservation", "recorded_by")
            .prefetch_related("reservation__items__room__hut")
        )

    @admin.display(description="Reservation")
    def reservation_link(self, obj):
        url = reverse("admin:bookings_reservation_change", args=[obj.reservation_id])
        return format_html('<a href="{}">{}</a>', url, obj.reservation.code)

    @admin.display(description="Guest", ordering="reservation__name")
    def guest_name(self, obj):
        return obj.reservation.name

    @admin.display(description="Hut")
    def hut_names(self, obj):
        return ", ".join(sorted({
            item.room.hut.name
            for item in obj.reservation.items.all()
            if item.room.hut_id
        })) or "—"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CancellationSettlement)
class CancellationSettlementAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    """Read-only cancellation decision and amounts at time of cancellation."""
    list_display = ("created", "reservation_link", "outcome", "net_received_at_cancellation",
                    "refunded_at_cancellation", "retained_at_cancellation", "recorded_by")
    list_filter = ("outcome", "created")
    search_fields = ("reservation__code", "reservation__name", "note")
    readonly_fields = ("reservation", "outcome", "net_received_at_cancellation",
                       "refunded_at_cancellation", "retained_at_cancellation", "method",
                       "note", "recorded_by", "created")
    fields = readonly_fields

    @admin.display(description="Reservation")
    def reservation_link(self, obj):
        return format_html('<a href="{}">{}</a>',
                           reverse("admin:bookings_reservation_change", args=[obj.reservation_id]),
                           obj.reservation.code)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reservation)
class ReservationAdmin(ProtectManagerAdmin, admin.ModelAdmin):
    list_display = [
        "name",
        "hut_name",
        "check_in",
        "check_out",
        "beds",
        "status",
        "deposit_due",
        "deposit_outstanding",
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
        "code", "created", "deposit_percentage", "deposit_due",
        "deposit_target", "deposit_paid", "deposit_outstanding", "deposit_state", "cancellation_link",
    ]

    fieldsets = (
        ("Guest and booking", {"fields": (
            "code", "name", "email", "phone", "notes", "check_in", "check_out",
            "status", "guest_request", "created",
        )}),
        ("Deposit information (calculated, read-only)", {"fields": (
            "deposit_percentage", "deposit_due", "deposit_target",
            "deposit_paid", "deposit_outstanding", "deposit_state", "cancellation_link",
        ), "description": (
            "Deposit requirements are set on the Hut admin page. "
            "Payment and refund history is shown below. "
            "Record transactions using the staff Payments screen."
        )}),
    )

    inlines = [ItemInline, DepositPaymentsInline]

    def get_inline_instances(self, request, obj=None):
        """Display the audit-only payment inline on existing reservation GETs.

        The inline is intentionally never writable. Including it in a POST
        requires its management-form fields, which breaks valid reservation
        saves (including the original admin add flow). Do not bind it on POST.
        """
        instances = super().get_inline_instances(request, obj)
        if request.method == "POST" or obj is None:
            return [inline for inline in instances if not isinstance(inline, DepositPaymentsInline)]
        return instances

    actions = ["cancel_with_deposit"]

    def get_urls(self):
        custom = [
            path("<path:object_id>/cancel-deposit/",
                 self.admin_site.admin_view(self.cancel_deposit_view),
                 name="bookings_reservation_cancel_deposit"),
        ]
        return custom + super().get_urls()

    def cancel_deposit_view(self, request, object_id):
        return cancellation_view(self, request, object_id)

    @admin.display(description="Cancellation and deposit")
    def cancellation_link(self, obj):
        if not obj or not obj.pk:
            return "—"
        settlement = CancellationSettlement.objects.filter(reservation=obj).first()
        if settlement:
            return format_html('<a href="{}">View settlement</a>',
                               reverse("admin:bookings_cancellationsettlement_change", args=[settlement.pk]))
        return format_html('<a href="{}">Cancel / handle deposit</a>',
                           reverse("admin:bookings_reservation_cancel_deposit", args=[obj.pk]))

    @admin.action(description="Cancel and handle deposit (one reservation at a time)")
    def cancel_with_deposit(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one reservation to review its deposit before cancelling.",
                              level="warning")
            return None
        reservation = queryset.first()
        return redirect(reverse("admin:bookings_reservation_cancel_deposit", args=[reservation.pk]))


    change_list_template = (
        "admin/bookings/reservation/change_list.html"
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("items__room__hut", "payment_transactions")
            .distinct()
        )

    def _deposit_info(self, obj):
        if not obj.pk:
            return None
        if not hasattr(obj, "_admin_deposit_info"):
            obj._admin_deposit_info = deposit_summary(obj)
        return obj._admin_deposit_info

    @admin.display(description="Deposit %")
    def deposit_percentage(self, obj):
        summary = self._deposit_info(obj)
        return f"{summary['percentage']}%" if summary else "—"

    @admin.display(description="Deposit due", ordering=None)
    def deposit_due(self, obj):
        summary = self._deposit_info(obj)
        return summary['due_date'] if summary else "—"

    @admin.display(description="Required deposit")
    def deposit_target(self, obj):
        summary = self._deposit_info(obj)
        return summary['target'] if summary else "—"

    @admin.display(description="Net paid (after refunds)")
    def deposit_paid(self, obj):
        summary = self._deposit_info(obj)
        return summary['net_paid'] if summary else "—"

    @admin.display(description="Deposit remaining")
    def deposit_outstanding(self, obj):
        summary = self._deposit_info(obj)
        return summary['remaining'] if summary else "—"

    @admin.display(description="Deposit status")
    def deposit_state(self, obj):
        summary = self._deposit_info(obj)
        if not summary:
            return "Unavailable (booking must belong to one hut)"
        if summary['remaining'] == 0:
            return "Deposit covered"
        if not summary['active']:
            return "Reservation inactive"
        return "Overdue" if summary['overdue'] else "Awaiting deposit"

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

