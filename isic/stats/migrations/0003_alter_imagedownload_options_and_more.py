# Generated by Django 4.1.13 on 2024-03-11 17:25
from __future__ import annotations

from django.db import migrations
import django_extensions.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ("stats", "0002_alter_imagedownload_user_agent"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="imagedownload",
            options={},
        ),
        migrations.RemoveField(
            model_name="imagedownload",
            name="modified",
        ),
        migrations.AlterField(
            model_name="imagedownload",
            name="created",
            field=django_extensions.db.fields.CreationDateTimeField(auto_now_add=True),
        ),
    ]
