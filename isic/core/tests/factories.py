import factory
import factory.django

from isic.core.models import Collection, Image
from isic.ingest.tests.factories import AccessionFactory


class ImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Image

    accession = factory.SubFactory(AccessionFactory)
    public = factory.Faker('boolean')


class CollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Collection

    name = factory.Faker('words')
    description = factory.Faker('paragraph')
