# Generated by Django 4.0.3 on 2022-04-14 13:27

import django.contrib.postgres.indexes
from django.db import migrations
import django.db.models.functions.text


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_auto_20220414_1324'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='collection',
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper('name'), name='gin_trgm_ops'
                ),
                name='collection_name_gin',
            ),
        ),
        migrations.AddIndex(
            model_name='image',
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper('isic'), name='gin_trgm_ops'
                ),
                name='isic_name_gin',
            ),
        ),
    ]
