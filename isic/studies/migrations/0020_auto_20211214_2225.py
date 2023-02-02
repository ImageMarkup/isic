# Generated by Django 3.2.9 on 2021-12-14 21:58

from django.db import migrations, models


def set_start_time(apps, schema_editor):
    Annotation = apps.get_model("studies", "Annotation")
    for annotation in Annotation.objects.filter(start_time=None):
        previous_annotation = (
            Annotation.objects.filter(
                study=annotation.study,
                annotator=annotation.annotator,
                created__lt=annotation.created,
            )
            .order_by("created")
            .last()
        )
        if previous_annotation:
            previous_time = previous_annotation.created
        else:
            previous_time = annotation.created

        annotation.start_time = previous_time
        annotation.save(update_fields=["start_time"])


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0019_annotation_start_time"),
    ]

    operations = [
        migrations.RunPython(set_start_time),
        migrations.AlterModelOptions(
            name="annotation",
            options={},
        ),
        migrations.AlterField(
            model_name="annotation",
            name="start_time",
            field=models.DateTimeField(),
        ),
        migrations.AddConstraint(
            model_name="annotation",
            constraint=models.CheckConstraint(
                check=models.Q(("start_time__lte", models.expressions.F("created"))),
                name="annotation_start_time_check",
            ),
        ),
    ]
