# Generated by Django 5.1.5 on 2025-02-18 21:08

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_alter_doi_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="doi",
            name="bundle_size",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
    ]
