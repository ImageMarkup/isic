# Generated by Django 4.1.10 on 2023-08-08 01:52

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0045_auto_20220703_0442"),
    ]

    operations = [
        migrations.AddField(
            model_name="doi",
            name="creator",
            field=models.ForeignKey(
                default=8, on_delete=django.db.models.deletion.RESTRICT, to=settings.AUTH_USER_MODEL
            ),
            preserve_default=False,
        ),
    ]
