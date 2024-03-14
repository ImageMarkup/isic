# Generated by Django 3.2 on 2021-05-19 22:47
from __future__ import annotations

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0001_initial_squashed"),
        ("core", "0003_alter_duplicateimage_accession"),
    ]

    operations = [
        migrations.CreateModel(
            name="Image",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                (
                    "isic_id",
                    models.CharField(
                        max_length=12,
                        unique=True,
                        validators=[django.core.validators.RegexValidator("^ISIC_[0-9]{7}$")],
                        verbose_name="ISIC ID",
                    ),
                ),
                ("public", models.BooleanField(default=False)),
                (
                    "accession",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT, to="ingest.accession"
                    ),
                ),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.AlterField(
            model_name="duplicateimage",
            name="isic_id",
            field=models.CharField(
                max_length=12,
                unique=True,
                validators=[django.core.validators.RegexValidator("^ISIC_[0-9]{7}$")],
                verbose_name="ISIC ID",
            ),
        ),
        migrations.CreateModel(
            name="ImageRedirect",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                (
                    "isic_id",
                    models.CharField(
                        max_length=12,
                        unique=True,
                        validators=[django.core.validators.RegexValidator("^ISIC_[0-9]{7}$")],
                        verbose_name="ISIC ID",
                    ),
                ),
                (
                    "image",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="redirects",
                        to="core.image",
                    ),
                ),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
    ]
