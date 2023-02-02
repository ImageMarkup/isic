# Generated by Django 3.2.11 on 2022-02-22 00:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0034_auto_20220217_1853'),
        ('studies', '0024_auto_20220222_0053'),
    ]

    operations = [
        migrations.AlterField(
            model_name='study',
            name='collection',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='studies',
                to='core.collection',
            ),
        ),
    ]
