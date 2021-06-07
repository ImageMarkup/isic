# Generated by Django 3.2.3 on 2021-06-07 13:05

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_auto_20210604_2116'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='girderdataset',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='girderimage',
            options={'ordering': ['item_id']},
        ),
        migrations.AlterField(
            model_name='girderimage',
            name='item_id',
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=24,
                unique=True,
                validators=[django.core.validators.RegexValidator('^[0-9a-f]{24}$')],
            ),
        ),
    ]
