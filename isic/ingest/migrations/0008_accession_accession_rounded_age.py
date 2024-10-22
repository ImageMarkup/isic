# Generated by Django 5.1.1 on 2024-10-05 04:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.expressions
import django.db.models.functions.comparison
import django.db.models.functions.math


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0007_accession_ingest_acce_fitzpat_15c454_idx_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                django.db.models.functions.comparison.Cast(
                    django.db.models.expressions.CombinedExpression(
                        django.db.models.functions.math.Round(
                            django.db.models.expressions.CombinedExpression(
                                django.db.models.functions.comparison.Cast(
                                    "age", output_field=models.FloatField()
                                ),
                                "/",
                                models.Value(5.0),
                            )
                        ),
                        "*",
                        models.Value(5),
                    ),
                    output_field=models.IntegerField(),
                ),
                name="accession_rounded_age",
            ),
        ),
    ]