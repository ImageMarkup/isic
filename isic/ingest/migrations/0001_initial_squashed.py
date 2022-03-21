from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import s3_file_field.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Accession',
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
                (
                    'girder_id',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text='The image_id from Girder.',
                        max_length=24,
                    ),
                ),
                ('original_blob', s3_file_field.fields.S3FileField()),
                ('blob_name', models.CharField(db_index=True, editable=False, max_length=255)),
                ('blob', s3_file_field.fields.S3FileField(blank=True)),
                (
                    'blob_size',
                    models.PositiveBigIntegerField(default=None, editable=False, null=True),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('creating', 'Creating'),
                            ('created', 'Created'),
                            ('skipped', 'Skipped'),
                            ('failed', 'Failed'),
                            ('succeeded', 'Succeeded'),
                        ],
                        default='creating',
                        max_length=20,
                    ),
                ),
                ('width', models.PositiveIntegerField(null=True)),
                ('height', models.PositiveIntegerField(null=True)),
                ('thumbnail_256', s3_file_field.fields.S3FileField(blank=True)),
                ('quality_check', models.BooleanField(db_index=True, null=True)),
                ('diagnosis_check', models.BooleanField(db_index=True, null=True)),
                ('phi_check', models.BooleanField(db_index=True, null=True)),
                ('duplicate_check', models.BooleanField(db_index=True, null=True)),
                ('lesion_check', models.BooleanField(db_index=True, null=True)),
                ('metadata', models.JSONField(default=dict)),
                ('unstructured_metadata', models.JSONField(default=dict)),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Cohort',
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
                (
                    'girder_id',
                    models.CharField(
                        blank=True, help_text='The dataset_id from Girder.', max_length=24
                    ),
                ),
                (
                    'name',
                    models.CharField(
                        help_text=(
                            'The name of your Cohort. <strong>This is private</strong>, '
                            'and will not be published along with your images.'
                        ),
                        max_length=255,
                    ),
                ),
                (
                    'description',
                    models.TextField(
                        help_text=(
                            'The description of your Cohort.<strong>This is private</strong>, '
                            'and will not be published along with your images.'
                        )
                    ),
                ),
                (
                    'copyright_license',
                    models.CharField(
                        choices=[('CC-0', 'CC-0'), ('CC-BY', 'CC-BY'), ('CC-BY-NC', 'CC-BY-NC')],
                        max_length=255,
                    ),
                ),
                (
                    'attribution',
                    models.CharField(
                        help_text='The institution name that should be attributed.', max_length=200
                    ),
                ),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ZipUpload',
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
                (
                    'blob',
                    s3_file_field.fields.S3FileField(
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=['zip']
                            )
                        ]
                    ),
                ),
                ('blob_name', models.CharField(editable=False, max_length=255)),
                ('blob_size', models.PositiveBigIntegerField(editable=False)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('created', 'Created'),
                            ('extracting', 'Extracting'),
                            ('extracted', 'Extracted'),
                            ('failed', 'Failed'),
                        ],
                        default='created',
                        max_length=20,
                    ),
                ),
                (
                    'cohort',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='zip_uploads',
                        to='ingest.cohort',
                    ),
                ),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MetadataFile',
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
                (
                    'blob',
                    s3_file_field.fields.S3FileField(
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=['csv']
                            )
                        ]
                    ),
                ),
                ('blob_name', models.CharField(editable=False, max_length=255)),
                ('blob_size', models.PositiveBigIntegerField(editable=False)),
                (
                    'cohort',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='metadata_files',
                        to='ingest.cohort',
                    ),
                ),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='DistinctnessMeasure',
            fields=[
                (
                    'id',
                    models.BigAutoField(
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
                    'checksum',
                    models.CharField(
                        blank=True,
                        db_index=True,
                        editable=False,
                        max_length=64,
                        null=True,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{64}$')],
                    ),
                ),
                (
                    'accession',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to='ingest.accession'
                    ),
                ),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Contributor',
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
                (
                    'institution_name',
                    models.CharField(
                        help_text=(
                            'The full name of your affiliated institution. '
                            '<strong>This is private</strong>, '
                            'and will not be published along with your images.'
                        ),
                        max_length=255,
                        verbose_name='Institution Name',
                    ),
                ),
                (
                    'institution_url',
                    models.URLField(
                        blank=True,
                        help_text=(
                            'The URL of your affiliated institution. '
                            '<strong>This is private</strong>, '
                            'and will not be published along with your images.'
                        ),
                        verbose_name='Institution URL',
                    ),
                ),
                (
                    'legal_contact_info',
                    models.TextField(
                        help_text=(
                            'The person or institution responsible for legal inquiries '
                            'about your data. '
                            '<strong> This is private</strong>, '
                            'and will not be published along with your images.'
                        ),
                        verbose_name='Legal Contact Information',
                    ),
                ),
                (
                    'default_copyright_license',
                    models.CharField(
                        blank=True,
                        choices=[('CC-0', 'CC-0'), ('CC-BY', 'CC-BY'), ('CC-BY-NC', 'CC-BY-NC')],
                        max_length=255,
                        verbose_name='Default Copyright License',
                    ),
                ),
                (
                    'default_attribution',
                    models.CharField(
                        blank=True,
                        help_text=(
                            'Text which must be reproduced by users of your images, '
                            'to comply with Creative Commons Attribution requirements.'
                        ),
                        max_length=255,
                        verbose_name='Default Attribution',
                    ),
                ),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='created_contributors',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'owners',
                    models.ManyToManyField(
                        related_name='owned_contributors', to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='cohort',
            name='contributor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='cohorts',
                to='ingest.contributor',
            ),
        ),
        migrations.AddField(
            model_name='cohort',
            name='creator',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.CreateModel(
            name='CheckLog',
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
                ('change_field', models.CharField(max_length=255)),
                ('change_to', models.BooleanField(null=True)),
                (
                    'accession',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='checklogs',
                        to='ingest.accession',
                    ),
                ),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='accession',
            name='cohort',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='accessions',
                to='ingest.cohort',
            ),
        ),
        migrations.AddField(
            model_name='accession',
            name='creator',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='accessions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='accession',
            name='zip_upload',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='accessions',
                to='ingest.zipupload',
            ),
        ),
        migrations.AddConstraint(
            model_name='cohort',
            constraint=models.UniqueConstraint(
                condition=models.Q(('girder_id', ''), _negated=True),
                fields=('girder_id',),
                name='cohort_unique_girder_id',
            ),
        ),
        migrations.AddConstraint(
            model_name='accession',
            constraint=models.UniqueConstraint(
                condition=models.Q(('girder_id', ''), _negated=True),
                fields=('girder_id',),
                name='accession_unique_girder_id',
            ),
        ),
        migrations.AddConstraint(
            model_name='accession',
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ('height__isnull', False), ('status', 'succeeded'), ('width__isnull', False)
                    ),
                    models.Q(('status', 'succeeded'), _negated=True),
                    _connector='OR',
                ),
                name='accession_wh_status_check',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='accession',
            unique_together={('cohort', 'blob_name')},
        ),
    ]
