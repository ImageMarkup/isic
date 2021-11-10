import djclick as click

from isic.core.models import GirderDataset, Image
from isic.core.models.collection import Collection
from isic.ingest.models.cohort import Cohort


@click.command(help='Migrate girder datasets to django collections')
def migrate_girder_datasets():
    with click.progressbar(GirderDataset.objects.all()) as items:
        for dataset in items:
            cohort = Cohort.objects.get(girder_id=dataset.id)
            if Image.objects.filter(accession__cohort=cohort).count() != dataset.images.count():
                print(dataset.name)

            coll, _ = Collection.objects.get_or_create(
                name=cohort.name,
                defaults={
                    'official': True,
                    'creator': cohort.creator,
                    'public': dataset.public,
                },
            )

            coll.images.set(Image.objects.filter(accession__cohort=cohort).all())

            assert (
                coll.public
                == set(
                    Image.objects.filter(accession__cohort=cohort).values_list('public', flat=True)
                ).pop()
            )
