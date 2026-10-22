from django.conf import settings
from django.db import models

class BedHousekeeping(models.Model):
    """Manual cleaning readiness, independent of reservations and closures."""
    bed = models.OneToOneField('bookings.Bed', on_delete=models.CASCADE, related_name='housekeeping')
    state = models.CharField(max_length=16, choices=[('needs_cleaning', 'Needs cleaning'), ('ready', 'Ready')], default='needs_cleaning')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ['bed__room_id', 'bed__number']
