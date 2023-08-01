# Generated by Django 4.1.10 on 2023-08-01 21:01

from django.db import migrations, transaction


def migrate_image_types(apps, schema_editor):
    Accession = apps.get_model("ingest", "Accession")

    with transaction.atomic():
        objs = []
        clinical_qs = Accession.objects.filter(metadata__image_type="clinical").select_for_update()

        for accession in clinical_qs.iterator():
            accession.metadata["image_type"] = "clinical close-up"
            objs.append(accession)

        overview_qs = Accession.objects.filter(metadata__image_type="overview").select_for_update()

        for accession in overview_qs.iterator():
            accession.metadata["image_type"] = "clinical overview"
            objs.append(accession)

        Accession.objects.bulk_update(objs, ["metadata"], batch_size=100)


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0039_alter_accession_copyright_license"),
    ]

    operations = [migrations.RunPython(migrate_image_types)]