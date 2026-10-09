from django.db import migrations


# Declining deletes these cookies on the isic-archive.com domain. On other hosts
# (e.g. localhost), browsers ignore that deletion, so existing _ga cookies stay.
# Consent tracking and GA gating work on every host.
def create_analytics_cookie_group(apps, schema_editor):
    CookieGroup = apps.get_model("cookie_consent", "CookieGroup")
    Cookie = apps.get_model("cookie_consent", "Cookie")

    group = CookieGroup.objects.create(
        varname="analytics",
        name="Analytics",
        description="Google Analytics cookies used to understand how the Archive is used.",
        is_required=False,
        is_deletable=True,
    )
    Cookie.objects.create(cookiegroup=group, name="_ga", domain="isic-archive.com")
    Cookie.objects.create(cookiegroup=group, name="_ga_VBHRJSWF1T", domain="isic-archive.com")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_squashed_0044_image_pin_nonnull"),
        ("cookie_consent", "0004_cookie_natural_key"),
    ]

    operations = [
        migrations.RunPython(
            create_analytics_cookie_group, migrations.RunPython.noop, elidable=False
        ),
    ]
