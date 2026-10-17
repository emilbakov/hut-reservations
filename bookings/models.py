
import secrets

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
    email = models.EmailField()
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
