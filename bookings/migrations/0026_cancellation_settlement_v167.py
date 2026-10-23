from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0025_deposit_admin_v166"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CancellationSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("outcome", models.CharField(choices=[("no_funds", "No funds received"), ("retain", "Retained funds"), ("refund", "Refund recorded")], max_length=12)),
                ("net_received_at_cancellation", models.DecimalField(decimal_places=2, max_digits=10)),
                ("refunded_at_cancellation", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("retained_at_cancellation", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("method", models.CharField(blank=True, choices=[("cash", "Cash"), ("bank", "Bank transfer"), ("card", "Card (external)"), ("other", "Other")], max_length=12)),
                ("note", models.CharField(blank=True, max_length=500)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("recorded_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recorded_cancellation_settlements", to=settings.AUTH_USER_MODEL)),
                ("reservation", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="cancellation_settlement", to="bookings.reservation")),
            ],
            options={"ordering": ["-created", "-pk"]},
        ),
        migrations.AddConstraint(model_name="cancellationsettlement", constraint=models.CheckConstraint(condition=Q(net_received_at_cancellation__gte=0), name="cancel_settlement_nonnegative_net")),
        migrations.AddConstraint(model_name="cancellationsettlement", constraint=models.CheckConstraint(condition=Q(refunded_at_cancellation__gte=0), name="cancel_settlement_nonnegative_refund")),
        migrations.AddConstraint(model_name="cancellationsettlement", constraint=models.CheckConstraint(condition=Q(retained_at_cancellation__gte=0), name="cancel_settlement_nonnegative_retained")),
    ]
