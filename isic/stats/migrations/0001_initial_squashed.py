from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions
import django_extensions.db.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('core', '0036_id_big_auto_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='GaMetrics',
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
                ('range_start', models.DateTimeField()),
                ('range_end', models.DateTimeField()),
                ('num_sessions', models.PositiveIntegerField()),
                ('sessions_per_country', models.JSONField()),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ImageDownload',
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
                ('download_time', models.DateTimeField()),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.CharField(max_length=200, null=True)),
                ('request_id', models.CharField(max_length=200, unique=True)),
                (
                    'image',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='downloads',
                        to='core.image',
                    ),
                ),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.AddConstraint(
            model_name='gametrics',
            constraint=models.CheckConstraint(
                check=models.Q(('range_start__lt', django.db.models.expressions.F('range_end'))),
                name='range_end_gt_range_start',
            ),
        ),
        migrations.AddConstraint(
            model_name='imagedownload',
            constraint=models.CheckConstraint(
                check=models.Q(('download_time__lt', django.db.models.expressions.F('created'))),
                name='download_occurred_before_tracking',
            ),
        ),
    ]
