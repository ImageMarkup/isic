from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    replaces = [
        ('login', '0001_default_site'),
        ('login', '0001_initial'),
        ('login', '0002_merge_default_site'),
        ('login', '0003_remove_profile_email_verified'),
        ('login', '0004_auto_20210609_1909'),
        ('login', '0004_user_profile'),
        ('login', '0005_profile_hash_id'),
        ('login', '0006_alter_profile_hash_id'),
        ('login', '0007_profile_accepted_terms'),
        ('login', '0008_id_big_auto_field'),
    ]

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'girder_id',
                    models.CharField(
                        blank=True,
                        max_length=24,
                        null=True,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^[0-9a-f]{24}$')],
                    ),
                ),
                ('girder_salt', models.CharField(blank=True, max_length=60)),
                (
                    'hash_id',
                    models.CharField(
                        max_length=5,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^[A-HJ-NP-Z2-9]{5}')],
                    ),
                ),
                ('accepted_terms', models.DateTimeField(null=True)),
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
    ]
