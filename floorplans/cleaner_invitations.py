"""V26 invitation model. Import CleanerInvitation in floorplans/models.py."""
import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


class CleanerInvitation(models.Model):
    hut = models.ForeignKey('bookings.Hut', on_delete=models.CASCADE, related_name='cleaner_invitations')
    email = models.EmailField(max_length=254)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['hut', 'email'])]

    @staticmethod
    def generate_token():
        token = secrets.token_urlsafe(36)
        return token, hashlib.sha256(token.encode('utf-8')).hexdigest()

    @property
    def is_pending(self):
        return not (self.accepted_at or self.revoked_at) and self.expires_at > timezone.now()

    @classmethod
    def expiry(cls):
        return timezone.now() + timedelta(days=3)
