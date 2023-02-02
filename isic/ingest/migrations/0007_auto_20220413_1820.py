# Generated by Django 4.0.3 on 2022-04-13 18:20

from django.db import migrations


def create_cohort_collections(apps, schema_editor):
    Accession = apps.get_model("ingest", "Accession")
    Cohort = apps.get_model("ingest", "Cohort")
    Collection = apps.get_model("core", "Collection")
    Image = apps.get_model("core", "Image")

    for cohort in Cohort.objects.filter(collection=None):
        try:
            first_published_accession = cohort.accessions.exclude(image=None).earliest("created")
        except Accession.DoesNotExist:
            continue

        cohort.collection = Collection.objects.create(
            # assume all images from a cohort have the same creator
            creator=first_published_accession.image.creator,
            name=f"Publish of {cohort.name}",
            description="",
            public=False,
            locked=False,
        )
        cohort.save(update_fields=["collection"])
        Collection.objects.filter(pk=cohort.collection.pk).update(
            created=first_published_accession.created
        )

        cohort.collection.images.add(
            *Image.objects.filter(accession__cohort=cohort).values_list("pk", flat=True)
        )
        cohort.collection.locked = True
        cohort.collection.save(update_fields=["locked"])


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0006_cohort_collection"),
    ]

    operations = [migrations.RunPython(create_cohort_collections)]
