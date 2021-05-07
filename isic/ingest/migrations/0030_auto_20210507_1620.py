# Generated by Django 3.2 on 2021-05-07 16:20

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0029_auto_20210428_0628'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='accession',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='checklog',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='cohort',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='contributor',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='metadatafile',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='zip',
            options={'ordering': ['created']},
        ),
        migrations.AlterField(
            model_name='accession',
            name='blob_name',
            field=models.CharField(db_index=True, editable=False, max_length=255),
        ),
        migrations.AlterField(
            model_name='accession',
            name='blob_size',
            field=models.PositiveBigIntegerField(default=None, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name='cohort',
            name='contributor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cohorts',
                to='ingest.contributor',
            ),
        ),
        migrations.AlterField(
            model_name='distinctnessmeasure',
            name='checksum',
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
                validators=[django.core.validators.RegexValidator('^[0-9a-f]{64}$')],
            ),
        ),
        migrations.AlterField(
            model_name='metadatafile',
            name='blob_name',
            field=models.CharField(editable=False, max_length=255),
        ),
        migrations.AlterField(
            model_name='metadatafile',
            name='blob_size',
            field=models.PositiveBigIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name='zip',
            name='blob_name',
            field=models.CharField(editable=False, max_length=255),
        ),
        migrations.AlterField(
            model_name='zip',
            name='blob_size',
            field=models.PositiveBigIntegerField(editable=False),
        ),
    ]
