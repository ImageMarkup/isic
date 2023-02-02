from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('login', '0007_profile_accepted_terms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='id',
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
            ),
        ),
    ]
