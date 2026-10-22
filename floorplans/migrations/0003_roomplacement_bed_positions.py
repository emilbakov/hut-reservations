from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("floorplans", "0002_floorfeature")]
    operations = [migrations.AddField(model_name="roomplacement", name="bed_positions", field=models.JSONField(default=list, blank=True))]
