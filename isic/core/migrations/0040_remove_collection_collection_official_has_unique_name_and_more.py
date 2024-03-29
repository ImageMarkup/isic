# Generated by Django 4.0.3 on 2022-04-07 17:12
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0039_alter_image_creator"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="collection",
            name="collection_official_has_unique_name",
        ),
        migrations.RenameField(
            model_name="collection",
            old_name="official",
            new_name="pinned",
        ),
        migrations.AddConstraint(
            model_name="collection",
            constraint=models.UniqueConstraint(
                condition=models.Q(("pinned", True)),
                fields=("name",),
                name="collection_pinned_has_unique_name",
            ),
        ),
    ]
