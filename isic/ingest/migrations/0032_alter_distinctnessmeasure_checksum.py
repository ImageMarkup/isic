# Generated by Django 3.2 on 2021-05-08 15:36

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0031_auto_20210507_2101'),
    ]

    operations = [
        migrations.AlterField(
            model_name='distinctnessmeasure',
            name='checksum',
            field=models.CharField(
                blank=True,
                db_index=True,
                editable=False,
                max_length=64,
                null=True,
                validators=[django.core.validators.RegexValidator('^[0-9a-f]{64}$')],
            ),
        ),
    ]
