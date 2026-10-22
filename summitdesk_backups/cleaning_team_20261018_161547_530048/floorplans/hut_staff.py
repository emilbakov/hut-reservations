"""V24 hut-scoped housekeeping staff membership."""
from django.conf import settings
from django.db import models

class HutCleaner(models.Model):
    hut = models.ForeignKey('bookings.Hut', on_delete=models.CASCADE, related_name='cleaner_memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hut_cleaner_memberships')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['hut', 'user'], name='unique_hut_cleaner')]
        ordering = ['user_id']
