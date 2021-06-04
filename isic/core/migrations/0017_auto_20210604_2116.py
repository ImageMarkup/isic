# Generated by Django 3.2.3 on 2021-06-04 21:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_alter_girderimage_status'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='girderimage',
            name='non_unknown_have_accession',
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
    ]
