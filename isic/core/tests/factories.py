import factory
import factory.django

from isic.core.models import Collection, Image
from isic.factories import UserFactory
from isic.ingest.tests.factories import AccessionFactory


class ImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Image

    created = factory.Faker("date_time")
    creator = factory.SubFactory(UserFactory)
    accession = factory.SubFactory(AccessionFactory)
    public = factory.Faker("boolean")


class CollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Collection

    creator = factory.SubFactory(UserFactory)
    name = factory.Faker("sentence")
    description = factory.Faker("paragraph")
    public = factory.Faker("boolean")
    pinned = factory.Faker("boolean")
    locked = False
