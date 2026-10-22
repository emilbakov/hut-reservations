"""V31 append-only reservation event records. Events begin after installation."""
from django.conf import settings
from django.db import models

class ReservationHistoryEvent(models.Model):
    hut = models.ForeignKey('bookings.Hut', on_delete=models.CASCADE, related_name='reservation_history')
    reservation = models.ForeignKey('bookings.Reservation', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_history')
    reservation_code = models.CharField(max_length=32, db_index=True)
    kind = models.CharField(max_length=40, db_index=True)
    description = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        indexes = [models.Index(fields=['hut', 'reservation_code', '-created_at'])]

    def __str__(self):
        return f'{self.reservation_code}: {self.kind}'
