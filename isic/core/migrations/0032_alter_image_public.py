# Generated by Django 3.2.9 on 2021-11-30 17:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_segmentation_segmentationreview'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='public',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]