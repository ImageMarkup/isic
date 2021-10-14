# Generated by Django 3.2.3 on 2021-08-27 14:41

from django.db import migrations, models
import django.db.models.deletion

import isic.core.models.isic_id


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_auto_20210814_0025'),
    ]

    operations = [
        migrations.AlterField(
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
    ]