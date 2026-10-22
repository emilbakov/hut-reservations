"""V24 hut-scoped housekeeping staff membership."""
from django.conf import settings
from django.db import models

class HutCleaner(models.Model):
    hut = models.ForeignKey('bookings.Hut', on_delete=models.CASCADE, related_name='cleaner_memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hut_cleaner_memberships')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['hut', 'user'], name='unique_hut_cleaner')]
        ordering = ['user_id']


class OfflineCleaner(models.Model):
    """A hut-scoped cleaning-team contact without a Django login account.

    Offline cleaners never gain authentication or staff permissions. A manager
    may assign them tasks and record progress on their behalf.
    """
    hut = models.ForeignKey(
        'bookings.Hut', on_delete=models.CASCADE,
        related_name='offline_cleaners',
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['hut', 'name'], name='unique_offline_cleaner_hut_name'
            ),
        ]

    def __str__(self):
        return self.name
