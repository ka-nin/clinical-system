from django.db import migrations, models


def urgent_to_priority(apps, schema_editor):
    Visit = apps.get_model("history", "Visit")
    Visit.objects.filter(urgent=True).update(priority="urgent")


def priority_to_urgent(apps, schema_editor):
    Visit = apps.get_model("history", "Visit")
    Visit.objects.filter(priority="urgent").update(urgent=True)


class Migration(migrations.Migration):
    dependencies = [("history", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="visit", name="priority",
            field=models.CharField(choices=[("normal", "Normal Level"), ("priority", "Priority Level"), ("urgent", "Urgent Level")],
                                   default="normal", max_length=10),
        ),
        migrations.RunPython(urgent_to_priority, priority_to_urgent),
        migrations.RemoveField(model_name="visit", name="urgent"),
    ]
