# Generated by Django 3.2.11 on 2022-03-05 08:44

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0034_auto_20220217_1853'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='name',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterUniqueTogether(
            name='collection',
            unique_together={('creator', 'name')},
        ),
        migrations.AddConstraint(
            model_name='collection',
            constraint=models.UniqueConstraint(
                condition=models.Q(('official', True)),
                fields=('name',),
                name='collection_official_has_unique_name',
            ),
        ),
    ]