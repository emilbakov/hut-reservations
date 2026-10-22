"""Audit/deduplication record for v129 daily manager emails."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0013_reservation_guest_request'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagerRequestDigestLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('digest_date', models.DateField()),
                ('recipient', models.EmailField(max_length=254)),
                ('hut_count', models.PositiveIntegerField(default=0)),
                ('request_count', models.PositiveIntegerField(default=0)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='request_digest_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-digest_date', '-sent_at'],
                'constraints': [models.UniqueConstraint(fields=('manager', 'digest_date'), name='unique_manager_request_digest_day')],
            },
        ),
    ]
