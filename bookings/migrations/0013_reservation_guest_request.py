"""Distinguish guest approval requests from short-lived payment holds."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0012_guestaccesslink_guestchangerequest")]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="guest_request",
            field=models.BooleanField(default=False, help_text="Public request awaiting manual hut approval; not a short payment hold."),
        ),
    ]
