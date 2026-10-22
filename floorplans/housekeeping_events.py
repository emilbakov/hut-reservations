from django.conf import settings
from django.db import models

class BedCleaningEvent(models.Model):
    bed = models.ForeignKey('bookings.Bed', on_delete=models.CASCADE, related_name='cleaning_events')
    action = models.CharField(max_length=20, choices=[('ready','Ready'),('needs_cleaning','Needs cleaning'),('checkout','Checkout')])
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.CharField(max_length=240, blank=True)
    reservation = models.ForeignKey('bookings.Reservation', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-created_at', '-pk']
