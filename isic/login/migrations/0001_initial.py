# Generated by Django 4.2.13 on 2024-06-25 19:44

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "girder_id",
                    models.CharField(
                        blank=True,
                        max_length=24,
                        null=True,
                        unique=True,
                        validators=[django.core.validators.RegexValidator("^[0-9a-f]{24}$")],
                    ),
                ),
                (
                    "hash_id",
                    models.CharField(
                        max_length=5,
                        unique=True,
                        validators=[django.core.validators.RegexValidator("^[A-HJ-NP-Z2-9]{5}$")],
                    ),
                ),
                ("accepted_terms", models.DateTimeField(null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
