# Generated by Django 3.2.6 on 2021-08-09 21:43
from __future__ import annotations

from django.db import migrations
import django_extensions.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0019_girderimage_pre_review"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="image",
            options={"get_latest_by": "created", "ordering": ["-created"]},
        ),
        migrations.AlterField(
            model_name="image",
            name="created",
            field=django_extensions.db.fields.CreationDateTimeField(
                auto_now_add=True, db_index=True
            ),
        ),
    ]
