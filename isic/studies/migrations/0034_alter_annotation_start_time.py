# Generated by Django 4.0.3 on 2022-05-25 16:35

from django.db import migrations, models
from django.db.models.expressions import F


def nullify_start_times(apps, schema_editor):
    Annotation = apps.get_model('studies', 'Annotation')

    # some annotations were filled with fake start times. particularly, the first
    # annotation for each study for each user. go back and nullify these now that
    # the constraint has been dropped.
    Annotation.objects.filter(created=F('start_time')).update(start_time=None)


class Migration(migrations.Migration):
    dependencies = [
        ('studies', '0033_response_value_alter_response_choice_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='annotation',
            name='start_time',
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(nullify_start_times),
    ]
