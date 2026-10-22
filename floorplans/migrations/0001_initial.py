from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [("bookings", "0001_initial")]
    operations = [migrations.CreateModel(name="RoomPlacement", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("floor", models.SmallIntegerField(default=0)),
        ("x", models.PositiveSmallIntegerField(default=0)),
        ("y", models.PositiveSmallIntegerField(default=0)),
        ("width", models.PositiveSmallIntegerField(default=2)),
        ("height", models.PositiveSmallIntegerField(default=2)),
        ("room", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="floor_placement", to="bookings.room")),
    ], options={"ordering": ["floor", "y", "x"]})]
