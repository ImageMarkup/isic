# Generated by Django 3.2.9 on 2021-11-10 00:08

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0028_delete_duplicateimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="creator",
            field=models.ForeignKey(
                default=1, on_delete=django.db.models.deletion.PROTECT, to="auth.user"
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="collection",
            name="official",
            field=models.BooleanField(default=False),
        ),
    ]
