# Generated by Django 5.1.5 on 2025-02-18 21:10

from django.db import migrations, models


def populate_bundle_size(apps, schema_editor):
    Doi = apps.get_model("core", "Doi")
    for doi in Doi.objects.all():
        if doi.bundle:
            doi.bundle_size = doi.bundle.size
            doi.save(update_fields=["bundle_size"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_doi_bundle_size"),
    ]

    operations = [
        migrations.RunPython(
            populate_bundle_size,
            elidable=True,
        ),
        migrations.AlterField(
            model_name="doi",
            name="bundle_size",
            field=models.PositiveBigIntegerField(null=True, blank=True),
        ),
    ]
