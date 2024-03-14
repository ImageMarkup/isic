# Generated by Django 4.0.3 on 2022-06-02 16:14
from __future__ import annotations

from django.db import migrations, models


def migrate_study_attributions(apps, schema_editor):
    Study = apps.get_model("studies", "Study")
    for study in Study.objects.all():
        if study.id == 92:
            study.attribution = (
                "ViDIR Group, Department of Dermatology, Medical University of Vienna"
            )
        elif study.id in [20, 21, 57, 90]:
            study.attribution = "ISIC Education Working Group"
        else:
            study.attribution = "Memorial Sloan Kettering Cancer Center"
        study.save(update_fields=["attribution"])


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0035_remove_response_response_choice_or_value_check_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="study",
            name="attribution",
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.RunPython(migrate_study_attributions),
    ]
