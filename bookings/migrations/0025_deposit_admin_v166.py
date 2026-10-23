# v166: admin-only proxy model; no database table or financial data changes.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("bookings", "0024_staff_decisions_v152")]

    operations = [
        migrations.CreateModel(
            name="DepositEntry",
            fields=[],
            options={
                "verbose_name": "Deposit",
                "verbose_name_plural": "Deposits",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("bookings.paymenttransaction",),
        ),
    ]
