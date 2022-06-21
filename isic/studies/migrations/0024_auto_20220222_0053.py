# Generated by Django 3.2.11 on 2022-02-22 00:53

from django.db import migrations


def create_base_collections(apps, schema_editor):
    Study = apps.get_model('studies', 'Study')
    Collection = apps.get_model('core', 'Collection')
    Image = apps.get_model('core', 'Image')

    for study in Study.objects.all():
        c = Collection.objects.create(
            creator=study.creator,
            name=f'Collection for {study.name}',
            public=study.public,
            official=False,
        )
        c.images.set(Image.objects.filter(studytask__study=study))
        c.locked = True
        c.save()
        study.collection = c
        study.save(update_fields=['collection'])


class Migration(migrations.Migration):

    dependencies = [
        ('studies', '0023_study_collection'),
    ]

    operations = [migrations.RunPython(create_base_collections)]
