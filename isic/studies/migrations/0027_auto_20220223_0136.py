# Generated by Django 3.2.11 on 2022-02-23 01:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_auto_20220217_1853'),
        ('studies', '0026_alter_study_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='study',
            name='collection',
            field=models.ForeignKey(
                help_text='The Collection of images to use in your Study.',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='studies',
                to='core.collection',
            ),
        ),
        migrations.AlterField(
            model_name='study',
            name='description',
            field=models.TextField(help_text='A description of the methodology behind your Study.'),
        ),
        migrations.AlterField(
            model_name='study',
            name='name',
            field=models.CharField(
                help_text='The name for your Study.', max_length=100, unique=True
            ),
        ),
        migrations.AlterField(
            model_name='study',
            name='public',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Whether or not your Study will be public. A study can only be '
                    'public if the images it uses are also public.'
                ),
            ),
        ),
    ]
