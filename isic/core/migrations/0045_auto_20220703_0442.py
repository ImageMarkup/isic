# Generated by Django 4.0.5 on 2022-07-03 04:42

from django.db import migrations


def setup_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")

    for group_name in ["Public", "ISIC Staff"]:
        Group.objects.get_or_create(name=group_name)

    public = Group.objects.get(name="Public")
    public.user_set.set(User.objects.all())


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0044_alter_isicoauthapplication_options"),
    ]

    operations = [
        migrations.RunPython(setup_groups),
    ]