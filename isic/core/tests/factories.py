import factory
import factory.django

from isic.core.models import Collection, Doi, Image
from isic.core.models.doi import DraftDoi
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
    public = factory.Faker("boolean")
    accession = factory.Maybe(
        "public",
        yes_declaration=factory.SubFactory(AccessionFactory, public=True),
        no_declaration=factory.SubFactory(AccessionFactory, public=False),
    )
    isic = factory.SubFactory(IsicIdFactory)


class CollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Collection

    creator = factory.SubFactory(UserFactory)
    name = factory.Faker("sentence")
    description = factory.Faker("paragraph")
    public = factory.Faker("boolean")
    pinned = factory.Maybe("public", yes_declaration=factory.Faker("boolean"), no_declaration=False)
    locked = False


class DoiFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Doi

    slug = factory.Faker("slug")
    collection = factory.SubFactory(CollectionFactory)
    creator = factory.SubFactory(UserFactory)


class DraftDoiFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DraftDoi

    slug = factory.Faker("slug")
    collection = factory.SubFactory(CollectionFactory)
    creator = factory.SubFactory(UserFactory)
