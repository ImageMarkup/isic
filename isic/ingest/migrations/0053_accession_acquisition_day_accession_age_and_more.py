# Generated by Django 4.1.13 on 2024-02-29 02:46
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0055_remove_accession_unstructured_metadata_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="accession",
            name="acquisition_day",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="age",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="anatom_site_general",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="benign_malignant",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="clin_size_long_diam_mm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="dermoscopic_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="diagnosis",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="diagnosis_confirm_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="family_hx_mm",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="image_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="mel_class",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="mel_mitotic_index",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="mel_thick_mm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="mel_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="mel_ulcer",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="melanocytic",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="nevus_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="personal_hx_mm",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="sex",
            field=models.CharField(blank=True, max_length=6, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="tbp_tile_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="fitzpatrick_skin_type",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
