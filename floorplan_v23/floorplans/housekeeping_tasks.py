"""V23 staff task tracking. Import HousekeepingTask from floorplans.models."""
from django.conf import settings
from django.db import models

class HousekeepingTask(models.Model):
    bed = models.ForeignKey('bookings.Bed', on_delete=models.CASCADE, related_name='housekeeping_tasks')
    day = models.DateField()
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_housekeeping_tasks')
    priority = models.CharField(max_length=8, choices=[('low','Low'),('normal','Normal'),('high','High')], default='normal')
    status = models.CharField(max_length=12, choices=[('open','Open'),('in_progress','In progress'),('done','Done')], default='open')
    note = models.CharField(max_length=240, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['bed','day'], name='unique_bed_housekeeping_task_day')]
        ordering = ['day','-priority','bed__room_id','bed__number']
