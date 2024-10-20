# Generated by Django 5.1.1 on 2024-10-03 00:43

from django.conf import settings
from django.db import migrations, models
import isic_metadata.diagnosis_hierarchical
import isic_metadata.fields


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0005_accession_legacy_dx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="accession",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "diagnosis__in",
                        isic_metadata.diagnosis_hierarchical.DiagnosisEnum,
                    )
                ),
                name="valid_diagnosis",
            ),
        ),
        migrations.AddConstraint(
            model_name="accession",
            constraint=models.CheckConstraint(
                condition=models.Q(("legacy_dx__in", isic_metadata.fields.LegacyDxEnum)),
                name="valid_legacy_dx",
            ),
        ),
    ]
