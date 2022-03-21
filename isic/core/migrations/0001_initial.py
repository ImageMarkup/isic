# Generated by Django 3.2 on 2021-04-26 19:51

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('ingest', '0001_initial_squashed'),
    ]

    operations = [
        migrations.CreateModel(
            name='DuplicateImage',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name='created'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    'girder_id',
                    models.CharField(
                        max_length=24,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{24}$')],
                    ),
                ),
                (
                    'isic_id',
                    models.CharField(
                        max_length=12,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^ISIC_[0-9]{7}$')],
                    ),
                ),
                ('metadata', models.JSONField(default=dict)),
                (
                    'accession',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='duplicates',
                        to='ingest.accession',
                    ),
                ),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
    ]
