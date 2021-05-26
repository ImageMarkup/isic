from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def set_contributor_owners(apps, schema_editor):
    Contributor = apps.get_model('ingest', 'Contributor')  # noqa: N806
    for contributor in Contributor.objects.all():
        contributor.owners.add(contributor.creator)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ingest', '0044_auto_20210525_0706'),
    ]

    operations = [
        migrations.AddField(
            model_name='contributor',
            name='owners',
            field=models.ManyToManyField(
                related_name='owned_contributors', to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterField(
            model_name='contributor',
            name='creator',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='created_contributors',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(set_contributor_owners),
    ]
