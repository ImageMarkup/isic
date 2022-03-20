from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions
import django_extensions.db.fields
import s3_file_field.fields

import isic.core.models.isic_id
from isic.core.search import maybe_create_index


def create_elasticsearch_index(apps, schema_editor):
    maybe_create_index()


class Migration(migrations.Migration):
    replaces = [
        ('core', '0001_initial'),
        ('core', '0002_alter_duplicateimage_accession'),
        ('core', '0003_alter_duplicateimage_accession'),
        ('core', '0004_auto_20210519_2247'),
        ('core', '0005_collection'),
        ('core', '0006_alter_collection_images'),
        ('core', '0007_isic_id'),
        ('core', '0008_auto_20210526_0232'),
        ('core', '0009_auto_20210602_1658'),
        ('core', '0010_auto_20210602_1835'),
        ('core', '0011_alter_girderimage_accession_id'),
        ('core', '0012_auto_20210603_2108'),
        ('core', '0013_auto_20210603_2311'),
        ('core', '0014_auto_20210604_0410'),
        ('core', '0015_auto_20210604_1420'),
        ('core', '0016_alter_girderimage_status'),
        ('core', '0017_auto_20210604_2116'),
        ('core', '0018_auto_20210607_1305'),
        ('core', '0019_girderimage_pre_review'),
        ('core', '0020_auto_20210809_2143'),
        ('core', '0020_auto_20210807_0228'),
        ('core', '0021_auto_20210814_0025'),
        ('core', '0022_alter_image_isic'),
        ('core', '0023_collection_public'),
        ('core', '0024_alter_imageredirect_image'),
        ('core', '0025_alter_imagealias_options'),
        ('core', '0026_auto_20211007_1737'),
        ('core', '0027_girderimage_raw'),
        ('core', '0028_delete_duplicateimage'),
        ('core', '0029_auto_20211110_0008'),
        ('core', '0030_alter_girderimage_accession'),
        ('core', '0031_segmentation_segmentationreview'),
        ('core', '0032_alter_image_public'),
        ('core', '0033_collection_locked'),
        ('core', '0034_auto_20220217_1853'),
        ('core', '0035_auto_20220305_0844'),
        ('core', '0036_id_big_auto_field'),
    ]

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('ingest', '0001_initial_squashed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Collection',
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
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('public', models.BooleanField(default=False)),
                ('official', models.BooleanField(default=False)),
                ('locked', models.BooleanField(default=False)),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Doi',
            fields=[
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
                    'id',
                    models.CharField(
                        max_length=30,
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.RegexValidator('^\\d+\\.\\d+/\\d+$')],
                    ),
                ),
                ('url', models.CharField(max_length=200)),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GirderDataset',
            fields=[
                (
                    'id',
                    models.CharField(
                        max_length=24,
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{24}$')],
                    ),
                ),
                ('name', models.CharField(max_length=255)),
                ('public', models.BooleanField()),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='Image',
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
                ('public', models.BooleanField(db_index=True, default=False)),
                (
                    'accession',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT, to='ingest.accession'
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
            name='IsicId',
            fields=[
                (
                    'id',
                    models.CharField(
                        default=isic.core.models.isic_id._default_id,
                        max_length=12,
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.RegexValidator('^ISIC_[0-9]{7}$')],
                        verbose_name='ISIC ID',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Segmentation',
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
                    'girder_id',
                    models.CharField(
                        max_length=24,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{24}$')],
                    ),
                ),
                ('mask', s3_file_field.fields.S3FileField(null=True)),
                ('meta', models.JSONField(default=dict)),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    'image',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT, to='core.image'
                    ),
                ),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='SegmentationReview',
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
                ('approved', models.BooleanField()),
                (
                    'skill',
                    models.CharField(
                        choices=[('novice', 'novice'), ('expert', 'expert')], max_length=6
                    ),
                ),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    'segmentation',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='reviews',
                        to='core.segmentation',
                    ),
                ),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ImageShare',
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
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='shares',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'image',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.image'),
                ),
                (
                    'recipient',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ImageAlias',
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
                    'image',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='aliases',
                        to='core.image',
                    ),
                ),
                (
                    'isic',
                    models.OneToOneField(
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        to='core.isicid',
                    ),
                ),
            ],
            options={
                'verbose_name_plural': 'Image aliases',
            },
        ),
        migrations.AddField(
            model_name='image',
            name='isic',
            field=models.OneToOneField(
                default=isic.core.models.isic_id.IsicId.safe_create,
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                to='core.isicid',
                verbose_name='isic id',
            ),
        ),
        migrations.AddField(
            model_name='image',
            name='shares',
            field=models.ManyToManyField(through='core.ImageShare', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='GirderImage',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('unknown', 'Unknown'),
                            ('non_image', 'Non-Image'),
                            ('corrupt', 'Corrupt'),
                            ('migrated', 'Migrated'),
                            ('true_duplicate', 'True Duplicate'),
                        ],
                        default='unknown',
                        max_length=30,
                    ),
                ),
                ('pre_review', models.BooleanField(null=True)),
                (
                    'item_id',
                    models.CharField(
                        db_index=True,
                        editable=False,
                        max_length=24,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{24}$')],
                    ),
                ),
                (
                    'file_id',
                    models.CharField(
                        editable=False,
                        max_length=24,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{24}$')],
                    ),
                ),
                ('original_filename', models.CharField(editable=False, max_length=255)),
                (
                    'original_file_relpath',
                    models.CharField(blank=True, editable=False, max_length=255),
                ),
                ('metadata', models.JSONField(blank=True, default=dict, editable=False)),
                (
                    'unstructured_metadata',
                    models.JSONField(blank=True, default=dict, editable=False),
                ),
                (
                    'original_blob_dm',
                    models.CharField(
                        editable=False,
                        max_length=64,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{64}$')],
                    ),
                ),
                (
                    'stripped_blob_dm',
                    models.CharField(
                        blank=True,
                        editable=False,
                        max_length=64,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{64}$')],
                    ),
                ),
                ('raw', models.JSONField(blank=True, null=True)),
                (
                    'accession',
                    models.OneToOneField(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to='ingest.accession',
                    ),
                ),
                (
                    'dataset',
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='images',
                        to='core.girderdataset',
                    ),
                ),
                (
                    'isic',
                    models.OneToOneField(
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        to='core.isicid',
                    ),
                ),
            ],
            options={
                'ordering': ['item_id'],
            },
        ),
        migrations.CreateModel(
            name='CollectionShare',
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
                    'collection',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to='core.collection'
                    ),
                ),
                (
                    'creator',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='collection_shares_given',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'recipient',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='collection_shares_received',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='collection',
            name='doi',
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.doi'
            ),
        ),
        migrations.AddField(
            model_name='collection',
            name='images',
            field=models.ManyToManyField(related_name='collections', to='core.image'),
        ),
        migrations.AddField(
            model_name='collection',
            name='shares',
            field=models.ManyToManyField(
                related_name='collection_shares',
                through='core.CollectionShare',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name='imageshare',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('creator', django.db.models.expressions.F('recipient')), _negated=True
                ),
                name='imageshare_creator_recipient_diff_check',
            ),
        ),
        migrations.AddConstraint(
            model_name='girderimage',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('status', 'unknown'),
                    ('status', 'non_image'),
                    ('accession__isnull', False),
                    _connector='OR',
                ),
                name='non_unknown_have_accession',
            ),
        ),
        migrations.AddConstraint(
            model_name='girderimage',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('status', 'non_image'),
                    models.Q(('stripped_blob_dm', ''), _negated=True),
                    _connector='OR',
                ),
                name='non_non_image_have_stripped_blob_dm',
            ),
        ),
        migrations.AddConstraint(
            model_name='collectionshare',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('creator', django.db.models.expressions.F('recipient')), _negated=True
                ),
                name='collectionshare_creator_recipient_diff_check',
            ),
        ),
        migrations.AddConstraint(
            model_name='collection',
            constraint=models.UniqueConstraint(
                condition=models.Q(('official', True)),
                fields=('name',),
                name='collection_official_has_unique_name',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='collection',
            unique_together={('creator', 'name')},
        ),
        migrations.RunPython(create_elasticsearch_index),
    ]
