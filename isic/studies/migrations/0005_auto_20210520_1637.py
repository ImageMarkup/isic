# Generated by Django 3.2 on 2021-05-20 16:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_initial_squashed'),
        ('studies', '0004_auto_20210520_0446'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='annotation',
            name='image',
        ),
        migrations.AlterField(
            model_name='annotation',
            name='image2',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.image'),
        ),
        migrations.AlterField(
            model_name='studytask',
            name='image2',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.image'),
        ),
        migrations.AlterUniqueTogether(
            name='studytask',
            unique_together={('study', 'annotator', 'image2')},
        ),
        migrations.RemoveField(
            model_name='studytask',
            name='image',
        ),
    ]
