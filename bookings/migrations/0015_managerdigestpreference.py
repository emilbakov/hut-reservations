"""Per-manager settings for the v129 daily email digest."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0014_managerrequestdigestlog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagerDigestPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True)),
                ('urgent_only', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('manager', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='digest_preference', to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
    ]
