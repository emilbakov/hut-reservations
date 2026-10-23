
import secrets

from django.conf import settings

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone


def make_code():
    """Unguessable reference used in the guest's booking link."""
    return secrets.token_urlsafe(9)


class Hut(models.Model):
    """A mountain hut containing rooms and beds."""

    public_phone = models.CharField(max_length=40, blank=True, validators=[RegexValidator(r"^\+?[0-9][0-9 ().-]{4,38}[0-9]$", "Enter a public phone number, including country code.")])
    public_email = models.EmailField(blank=True)
    directions_url = models.URLField(max_length=500, blank=True, validators=[URLValidator(schemes=["http", "https"])], help_text="Actual hut location/directions link. Never the operator's office location.")
    reply_time_en = models.CharField(max_length=300, blank=True, help_text="A realistic reply expectation, e.g. during staffed hours. Leave blank if not agreed.")
    reply_time_bg = models.CharField(max_length=300, blank=True)
    payment_instructions_en = models.TextField(blank=True, help_text="Actual payment methods, timing and any deposit rules. Public plain text; no card details.")
    payment_instructions_bg = models.TextField(blank=True)

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


class HutQuickReply(models.Model):
    """Reusable, manager-editable reply for a single hut (v134)."""
    hut = models.ForeignKey(Hut, on_delete=models.CASCADE, related_name='quick_replies')
    title = models.CharField(max_length=80)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title', 'pk']
        constraints = [models.UniqueConstraint(fields=['hut', 'title'], name='unique_hut_quick_reply')]

    def __str__(self):
        return f'{self.hut}: {self.title}'


class GuestConversationMessage(models.Model):
    """Reservation-scoped guest/manager conversation, independent of email replies."""
    class Sender(models.TextChoices):
        GUEST = 'guest', 'Guest'
        MANAGER = 'manager', 'Manager'

    class Delivery(models.TextChoices):
        RECEIVED = 'received', 'Received in SummitDesk'
        IN_APP = 'in_app', 'In-app only'
        SENDING = 'sending', 'Email sending'
        SENT = 'sent', 'Email submitted'
        FAILED = 'failed', 'Email failed (in-app delivered)'

    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE, related_name='conversation_messages')
    hut = models.ForeignKey(Hut, on_delete=models.PROTECT, related_name='conversation_messages')
    sender = models.CharField(max_length=10, choices=Sender.choices)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sent_guest_conversation_messages')
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    recipient = models.EmailField(blank=True)
    delivery = models.CharField(max_length=12, choices=Delivery.choices)
    error = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    email_message_id = models.CharField(
    max_length=255,
    null=True,
    blank=True,
    unique=True,
    help_text="Unique Message-ID of an imported email.",
    )

    email_received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of an incoming email.",
    )


    class Meta:
        ordering = ['created_at', 'pk']
        indexes = [models.Index(fields=['reservation', 'created_at'], name='guest_conversation_idx')]

class EmailSyncState(models.Model):
    """Track Gmail IMAP synchronization progress."""

    mailbox = models.EmailField(unique=True)

    uidvalidity = models.BigIntegerField(
        default=0,
    )

    last_uid = models.BigIntegerField(
        default=0,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.mailbox} (UID {self.last_uid})"   


class PreArrivalReminder(models.Model):
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name="pre_arrival_reminder",
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"Pre-arrival reminder for {self.reservation.code}"             


class PublicBookingSubmission(models.Model):
    """A browser-scoped idempotency record, committed with its booking."""
    key = models.CharField(max_length=64, unique=True)
    payload_hash = models.CharField(max_length=64)
    reservation = models.ForeignKey(Reservation, null=True, blank=True, on_delete=models.SET_NULL)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class ReservationNotification(models.Model):
    """Durable delivery state; private message bodies never appear in staff UI."""
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='delivery_notifications')
    dedupe_key = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=32)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=12, default='pending', choices=[('pending', 'Queued'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Not needed')])
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'next_attempt_at'], name='sd145_notification_due')]


class PublicWebsiteSettings(models.Model):
    """One owner-managed public profile; blank contact details stay private."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    brand_name = models.CharField(max_length=80, blank=True)
    operator_name = models.CharField(max_length=200, blank=True, help_text="Legal operator / data controller, for published policies.")
    contact_phone = models.CharField(max_length=40, blank=True)
    contact_email = models.EmailField(blank=True)
    privacy_email = models.EmailField(blank=True)
    address_en = models.CharField(max_length=300, blank=True)
    address_bg = models.CharField(max_length=300, blank=True)
    map_url = models.URLField(max_length=500, blank=True, help_text="Public HTTPS map link; no embedded third-party map.")
    hero_image = models.ImageField(upload_to="site/", blank=True, width_field="hero_width", height_field="hero_height", help_text="Your own licensed landscape, at least 1920 px wide, up to 12 MB. Prefer optimized WebP.")
    hero_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    hero_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    hero_alt_en = models.CharField(max_length=200, blank=True)
    hero_alt_bg = models.CharField(max_length=200, blank=True)
    privacy_en = models.TextField(blank=True, help_text="Reviewed plain text. Include operator, purposes, legal bases, recipients, retention, rights and complaint details.")
    privacy_bg = models.TextField(blank=True)
    privacy_published = models.BooleanField(default=False)
    cancellation_en = models.TextField(blank=True, help_text="Reviewed terms, including hut-specific rules, deadlines, fees and refunds where applicable.")
    cancellation_bg = models.TextField(blank=True)
    cancellation_published = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Public website settings"
        verbose_name_plural = "Public website settings"
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="sd149_single_public_profile")]

    def __str__(self):
        return "Public website settings"

    def clean(self):
        import re
        from django.core.validators import URLValidator
        errors = {}
        if self.pk != 1:
            errors["id"] = "Only one public website profile is supported."
        if self.contact_phone and not re.fullmatch(r"\+?[0-9 () .-]{6,40}", self.contact_phone):
            errors["contact_phone"] = "Use a phone number with digits, spaces, +, brackets or dashes."
        if self.map_url:
            try:
                URLValidator(schemes=["https", "http"])(self.map_url)
            except ValidationError:
                errors["map_url"] = "Use an HTTP or HTTPS map link."
        if self.hero_image:
            if not self.hero_width or self.hero_width < 1920:
                errors["hero_image"] = "The original image must be at least 1920 px wide. Do not upscale a small photo."
            if not (self.hero_alt_en.strip() or self.hero_alt_bg.strip()):
                errors["hero_alt_en"] = "Describe the image in at least one language."
            if not self.hero_image._committed and self.hero_image.size > 12 * 1024 * 1024:
                errors["hero_image"] = "Upload an image smaller than 12 MB."
        for kind in ("privacy", "cancellation"):
            if getattr(self, kind + "_published"):
                if not self.operator_name.strip():
                    errors["operator_name"] = "Name the operator before publishing policies."
                if not any(getattr(self, kind + "_" + lang).strip() for lang in ("en", "bg")):
                    errors[kind + "_en"] = "Enter reviewed policy text in at least one language before publishing."
        if self.privacy_published and not (self.privacy_email or self.contact_email):
            errors["privacy_email"] = "Provide a privacy contact email before publishing."
        if errors:
            raise ValidationError(errors)


class PublicBookingRateBucket(models.Model):
    """Short-lived HMAC identifiers; no raw email, IP or browser secret."""
    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
