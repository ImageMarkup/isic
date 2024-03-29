# Generated by Django 3.2.3 on 2021-06-04 14:20
from __future__ import annotations

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0014_auto_20210604_0410"),
    ]

    operations = [
        migrations.AlterField(
            model_name="girderimage",
            name="status",
            field=models.CharField(
                choices=[
                    ("unknown", "Unknown`"),
                    ("non_image", "Non-Image`"),
                    ("corrupt", "Corrupt"),
                    ("migrated", "Migrated"),
                    ("true_duplicate", "True Duplicate"),
                ],
                default="unknown",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="girderimage",
            name="stripped_blob_dm",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                validators=[django.core.validators.RegexValidator("^[0-9a-f]{64}$")],
            ),
        ),
        migrations.AddConstraint(
            model_name="girderimage",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("status", "non_image"),
                    models.Q(("stripped_blob_dm", ""), _negated=True),
                    _connector="OR",
                ),
                name="non_non_image_have_stripped_blob_dm",
            ),
        ),
    ]
