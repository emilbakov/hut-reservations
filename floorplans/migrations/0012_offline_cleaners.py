"""Name-only cleaning team members and task assignments."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('floorplans', '0011_reservationhistoryevent_changes'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfflineCleaner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('hut', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offline_cleaners', to='bookings.hut')),
            ],
            options={
                'ordering': ['name', 'pk'],
                'constraints': [models.UniqueConstraint(fields=('hut', 'name'), name='unique_offline_cleaner_hut_name')],
            },
        ),
        migrations.AddField(
            model_name='housekeepingtask',
            name='offline_assignee',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_housekeeping_tasks', to='floorplans.offlinecleaner'),
        ),
    ]
