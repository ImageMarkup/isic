# Generated by Django 3.2 on 2021-05-25 07:06
from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0007_auto_20210520_1643"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="feature",
            options={"get_latest_by": "modified", "ordering": ["name"]},
        ),
        migrations.AlterModelOptions(
            name="question",
            options={"get_latest_by": "modified", "ordering": ["prompt"]},
        ),
        migrations.AlterModelOptions(
            name="study",
            options={"get_latest_by": "modified", "verbose_name_plural": "Studies"},
        ),
        migrations.AlterModelOptions(
            name="studytask",
            options={"get_latest_by": "modified"},
        ),
    ]
