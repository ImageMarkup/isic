# Generated by Django 3.2.3 on 2021-06-04 04:10
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_auto_20210603_2311"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="girderimage",
            name="non_unknown_have_accession_id",
        ),
        migrations.AddConstraint(
            model_name="girderimage",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("status", "unknown"), ("accession__isnull", False), _connector="OR"
                ),
                name="non_unknown_have_accession",
            ),
        ),
    ]
