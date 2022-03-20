# Generated by Django 3.2 on 2021-05-20 16:43

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial_squashed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('studies', '0006_delete_image'),
    ]

    operations = [
        migrations.RenameField(
            model_name='annotation',
            old_name='image2',
            new_name='image',
        ),
        migrations.RenameField(
            model_name='studytask',
            old_name='image2',
            new_name='image',
        ),
        migrations.AlterUniqueTogether(
            name='studytask',
            unique_together={('study', 'annotator', 'image')},
        ),
    ]
