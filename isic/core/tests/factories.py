import factory
import factory.django

from isic.core.models import Collection, Doi, Image
from isic.core.models.isic_id import IsicId
from isic.factories import UserFactory
from isic.ingest.tests.factories import AccessionFactory


class IsicIdFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IsicId

    id = factory.Faker("pystr_format", string_format="ISIC_#######")


class ImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Image

    created = factory.Faker("date_time")
    creator = factory.SelfAttribute("accession.creator")
    accession = factory.SubFactory(AccessionFactory)
    public = factory.Faker("boolean")
    isic = factory.SubFactory(IsicIdFactory)


class CollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Collection

    creator = factory.SubFactory(UserFactory)
    name = factory.Faker("sentence")
    description = factory.Faker("paragraph")
    public = factory.Faker("boolean")
    pinned = factory.Faker("boolean")
    locked = False


class DoiFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Doi

    slug = factory.Faker("slug")
    creator = factory.SubFactory(UserFactory)
