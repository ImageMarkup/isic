# Generated by Django 4.1.13 on 2024-02-26 15:31
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0051_rename_primary_biopsy_accession_concomitant_biopsy"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="accession",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("concomitant_biopsy", True),
                        ("metadata__diagnosis_confirm_type", "histopathology"),
                    ),
                    models.Q(("concomitant_biopsy", True), _negated=True),
                    _connector="OR",
                ),
                name="accession_concomitant_biopsy_diagnosis_confirm_type",
            ),
        ),
    ]
