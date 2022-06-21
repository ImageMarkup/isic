from django.db import migrations


def ensure_profile(apps, schema_editor):
    """Add missing Profiles, due to a bug where they were sometimes not created."""
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('login', 'Profile')

    for user in User.objects.filter(profile=None):
        Profile.objects.create(user=user)


class Migration(migrations.Migration):
    dependencies = [
        ('login', '0004_auto_20210609_1909'),
    ]

    operations = [migrations.RunPython(ensure_profile)]
