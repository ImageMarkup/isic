# Generated by Django 3.2.11 on 2022-02-17 18:53

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions
import django_extensions.db.fields


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0033_collection_locked'),
    ]

    operations = [
        migrations.CreateModel(
            name='CollectionShare',
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
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
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
        migrations.AddField(
            model_name='collectionshare',
            name='collection',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to='core.collection'
            ),
        ),
        migrations.AddField(
            model_name='collectionshare',
            name='creator',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='collection_shares_given',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='collectionshare',
            name='recipient',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='collection_shares_received',
                to=settings.AUTH_USER_MODEL,
            ),
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
            model_name='collectionshare',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('creator', django.db.models.expressions.F('recipient')), _negated=True
                ),
                name='collectionshare_creator_recipient_diff_check',
            ),
        ),
    ]
