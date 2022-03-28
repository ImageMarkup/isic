# Generated by Django 4.0.3 on 2022-03-28 04:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


def create_initial_metadata_revisions(apps, schema_editor):
    Accession = apps.get_model('ingest', 'Accession')  # noqa: N806
    User = apps.get_model('auth', 'User')  # noqa: N806
    accessions = Accession.objects.exclude(metadata={}, unstructured_metadata={})
    if accessions.exists():
        user = User.objects.get(pk=1)
        for accession in accessions:
            accession.metadata_revisions.create(
                creator=user,
                metadata=accession.metadata,
                unstructured_metadata=accession.unstructured_metadata,
            )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ingest', '0002_remove_accession_accession_wh_status_check_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetadataRevision',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, db_index=True
                    ),
                ),
                ('metadata', models.JSONField()),
                ('unstructured_metadata', models.JSONField()),
                (
                    'accession',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='metadata_revisions',
                        to='ingest.accession',
                    ),
                ),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='metadata_revisions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
        migrations.RunPython(create_initial_metadata_revisions),
    ]
