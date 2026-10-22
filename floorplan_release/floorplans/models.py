from django.db import models

class RoomPlacement(models.Model):
    room = models.OneToOneField("bookings.Room", on_delete=models.CASCADE, related_name="floor_placement")
    floor = models.SmallIntegerField(default=0)
    x = models.PositiveSmallIntegerField(default=0)
    y = models.PositiveSmallIntegerField(default=0)
    width = models.PositiveSmallIntegerField(default=2)
    height = models.PositiveSmallIntegerField(default=2)

    class Meta:
        ordering = ["floor", "y", "x"]
