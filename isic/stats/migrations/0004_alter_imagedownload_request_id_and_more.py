# Generated by Django 4.1.13 on 2024-03-11 18:51
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("stats", "0003_alter_imagedownload_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="imagedownload",
            name="request_id",
            field=models.CharField(max_length=200),
        ),
        migrations.AddConstraint(
            model_name="imagedownload",
            constraint=models.UniqueConstraint(fields=("request_id",), name="unique_request_id"),
        ),
    ]
