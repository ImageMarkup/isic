# Generated by Django 3.2.9 on 2021-12-14 21:20
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0018_auto_20211129_0737"),
    ]

    operations = [
        migrations.AddField(
            model_name="annotation",
            name="start_time",
            field=models.DateTimeField(null=True),
        ),
    ]
