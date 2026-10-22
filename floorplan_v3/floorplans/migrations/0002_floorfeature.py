from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("floorplans", "0001_initial")]
    operations = [migrations.CreateModel(name="FloorFeature", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("floor", models.SmallIntegerField(default=0)),
        ("kind", models.CharField(max_length=12, choices=[("stairs", "Stairs"), ("corridor", "Corridor"), ("door", "Door")])),
        ("x", models.PositiveSmallIntegerField()), ("y", models.PositiveSmallIntegerField()),
        ("width", models.PositiveSmallIntegerField(default=1)), ("height", models.PositiveSmallIntegerField(default=1)),
        ("hut", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="floor_features", to="bookings.hut")),
    ], options={"ordering": ["floor", "y", "x", "pk"]})]
