
import secrets

from django.conf import settings

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.urls import reverse


def make_code():
    """Unguessable reference used in the guest's booking link."""
    return secrets.token_urlsafe(9)


class Hut(models.Model):
    """A mountain hut containing rooms and beds."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    image = models.ImageField(
        upload_to="huts/",
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="managed_huts",
        help_text="Staff accounts allowed to view this hut dashboard.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Room(models.Model):
    """A room belonging to a mountain hut."""

    hut = models.ForeignKey(
        Hut,
        on_delete=models.PROTECT,
        related_name="rooms",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True)

    capacity = models.PositiveIntegerField(
        help_text="Number of beds in the room."
    )

    price_per_night = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        help_text="Price per bed, per night.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Untick to stop taking new bookings for this room.",
    )

    position = models.PositiveIntegerField(
        default=0,
        help_text="Order on the booking page.",
    )

    class Meta:
        ordering = ["hut_id", "position", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["hut", "name"],
                name="unique_room_name_per_hut",
            )
        ]

    def clean(self):
        if self.capacity < 1:
            raise ValidationError({
                "capacity": "A room must have at least one bed."
            })

    def __str__(self):
        if self.hut_id:
            return f"{self.hut.name} — {self.name}"
        return self.name


class Reservation(models.Model):
    """A guest reservation for one or more rooms."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    HOLDING = [Status.PENDING, Status.CONFIRMED]

    code = models.CharField(
        max_length=16,
        unique=True,
        default=make_code,
        editable=False,
    )

    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    check_in = models.DateField()

    check_out = models.DateField(
        help_text="Day of departure (not a booked night)."
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )

    guest_request = models.BooleanField(
        default=False,
        help_text="Public request awaiting manual hut approval; not a short payment hold.",
    )

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-check_in", "-created"]
        constraints = [
            models.CheckConstraint(
                condition=Q(check_out__gt=F("check_in")),
                name="check_out_after_check_in",
            ),
        ]
        indexes = [
            models.Index(fields=["check_in", "check_out"])
        ]

    def __str__(self):
        return f"{self.name}, {self.check_in} to {self.check_out}"

    def clean(self):
        if (
            self.check_in
            and self.check_out
            and self.check_out <= self.check_in
        ):
            raise ValidationError({
                "check_out": "Check-out must be after check-in."
            })

    def get_absolute_url(self):
        return reverse(
            "bookings:reservation",
            args=[self.code],
        )

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    @property
    def total_beds(self):
        return sum(
            item.beds for item in self.items.all()
        )

    @property
    def total_price(self):
        return sum(
            item.subtotal for item in self.items.all()
        )


class ReservationItem(models.Model):
    """
    A number of beds reserved in one room.
    Bunks are assigned on arrival.
    """

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="items",
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="items",
    )

    beds = models.PositiveIntegerField()

    price_per_night = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        help_text="Price per bed, per night, at the time of booking.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["reservation", "room"],
                name="one_item_per_room",
            ),
            models.CheckConstraint(
                condition=Q(beds__gte=1),
                name="at_least_one_bed",
            ),
        ]

    def __str__(self):
        return f"{self.beds} x {self.room}"

    @property
    def subtotal(self):
        return (
            self.beds
            * self.price_per_night
            * self.reservation.nights
        )


class GuestStay(models.Model):
    """Actual arrival/departure events, separate from booking dates/status."""
    reservation = models.OneToOneField(
        Reservation, on_delete=models.CASCADE, related_name="guest_stay"
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="guest_checkins"
    )
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="guest_checkouts"
    )

    def __str__(self):
        return f"Stay for {self.reservation.code}"


class Bed(models.Model):
    """A numbered physical bed. A room's capacity remains the booking limit."""
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='individual_beds')
    number = models.PositiveIntegerField()

    class Meta:
        ordering = ['room_id', 'number']
        constraints = [models.UniqueConstraint(fields=['room', 'number'], name='unique_numbered_bed_per_room')]

    def __str__(self):
        return f'{self.room} / Bed {self.number}'


class BedAssignment(models.Model):
    """A bed assigned to one reservation item for the reservation's full stay."""
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name='assignments')
    item = models.ForeignKey(ReservationItem, on_delete=models.CASCADE, related_name='bed_assignments')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['bed', 'item'], name='unique_bed_assignment_item')]


class BedClosure(models.Model):
    """Bed unavailable on nights in [start, end)."""
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name='closures')
    start = models.DateField()
    end = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(end__gt=F('start')), name='bed_closure_end_after_start')]

class PaymentTransaction(models.Model):
    """Append-only manual ledger; positive amounts for receipts and refunds."""
    class Kind(models.TextChoices):
        PAYMENT = 'payment', 'Payment'
        DEPOSIT = 'deposit', 'Deposit'
        REFUND = 'refund', 'Refund'

    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK = 'bank', 'Bank transfer'
        CARD = 'card', 'Card (external)'
        OTHER = 'other', 'Other'

    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT, related_name='payment_transactions')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    method = models.CharField(max_length=12, choices=Method.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=500, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_hut_payments')

    class Meta:
        ordering = ['-created', '-pk']
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name='payment_transaction_positive')]

    def __str__(self):
        return f'{self.kind} {self.amount} for {self.reservation.code}'

class HutExpense(models.Model):
    """Recorded operational expense, allocated to one hut and expense date."""
    class Category(models.TextChoices):
        FOOD = 'food', 'Food and supplies'
        UTILITIES = 'utilities', 'Electricity and utilities'
        HEATING = 'heating', 'Heating and fuel'
        MAINTENANCE = 'maintenance', 'Maintenance'
        STAFF = 'staff', 'Staff costs'
        TRANSPORT = 'transport', 'Transport'
        OTHER = 'other', 'Other'

    hut = models.ForeignKey(Hut, on_delete=models.PROTECT, related_name='expenses')
    category = models.CharField(max_length=20, choices=Category.choices)
    expense_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=250)
    reference = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_hut_expenses')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-pk']
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name='hut_expense_positive')]
        indexes = [models.Index(fields=['hut', 'expense_date'])]

    def __str__(self):
        return f'{self.hut}: {self.amount} ({self.category})'

class HutDepositPolicy(models.Model):
    grace_days = models.PositiveSmallIntegerField(default=2)
    auto_cancel_enabled = models.BooleanField(default=False)

    """Per-hut deposit requirement and payment deadline."""
    hut = models.OneToOneField(Hut, on_delete=models.CASCADE, related_name='deposit_policy')
    percentage = models.PositiveSmallIntegerField(default=30)
    due_days = models.PositiveSmallIntegerField(default=3)
    reminders_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(percentage__lte=100), name='deposit_percentage_max_100')]

    def clean(self):
        if self.percentage > 100:
            raise ValidationError({'percentage': 'Percentage cannot exceed 100.'})


class DepositReminderLog(models.Model):
    """One reminder per reservation and due date, to avoid repeated emails."""
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='deposit_reminders')
    due_date = models.DateField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['reservation', 'due_date'], name='unique_deposit_reminder_due_date')]


class ReservationLifecycleEvent(models.Model):
    """Audit trail for deposit deadline warnings and automated cancellations."""
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="lifecycle_events")
    event_type = models.CharField(max_length=30, choices=[
        ("warning", "Warning issued"), ("cancelled", "Automatically cancelled"),
    ])
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    details = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["reservation", "event_type", "due_date"],
                                    name="unique_lifecycle_event_per_due_date")
        ]

class HutMessageTemplate(models.Model):
    """Optional per-hut email text; blank means use built-in default."""
    TYPES = [
        ("confirmation", "Confirmation"),
        ("deposit_due", "Deposit due"),
        ("deposit_overdue", "Deposit overdue"),
        ("prearrival", "Pre-arrival"),
        ("cancellation", "Cancellation"),
    ]
    hut = models.ForeignKey(Hut, on_delete=models.CASCADE, related_name="message_templates")
    message_type = models.CharField(max_length=25, choices=TYPES)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["hut", "message_type"], name="unique_hut_message_template")
        ]


class GuestMessageLog(models.Model):
    """Delivery record, one message per reservation/type/relevant date."""
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="guest_messages")
    hut = models.ForeignKey(Hut, on_delete=models.PROTECT)
    message_type = models.CharField(max_length=25, choices=HutMessageTemplate.TYPES)
    event_date = models.DateField()
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=[("sent", "Sent"), ("failed", "Failed")])
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["reservation", "message_type", "event_date"],
                                    name="unique_guest_message_event")
        ]


def make_guest_access_token():
    import secrets
    return secrets.token_urlsafe(32)


class GuestAccessLink(models.Model):
    """Separate revocable, high-entropy guest access token."""
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name="guest_access")
    token = models.CharField(max_length=64, unique=True, default=make_guest_access_token, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class GuestChangeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved for manual processing"
        REJECTED = "rejected", "Rejected"

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="guest_change_requests")
    request_type = models.CharField(max_length=20, choices=[
        ("change", "Change request"), ("cancellation", "Cancellation request")
    ])
    requested_check_in = models.DateField(null=True, blank=True)
    requested_check_out = models.DateField(null=True, blank=True)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="reviewed_guest_requests")
    manager_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class ManagerRequestDigestLog(models.Model):
    """At most one successfully submitted manager digest per local day."""
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='request_digest_logs',
    )
    digest_date = models.DateField()
    recipient = models.EmailField()
    hut_count = models.PositiveIntegerField(default=0)
    request_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-digest_date', '-sent_at']
        constraints = [models.UniqueConstraint(
            fields=['manager', 'digest_date'],
            name='unique_manager_request_digest_day',
        )]


class ManagerDigestPreference(models.Model):
    """Manager's personal daily email reminder preferences (v130)."""
    manager = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='digest_preference',
    )
    enabled = models.BooleanField(default=True)
    urgent_only = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
