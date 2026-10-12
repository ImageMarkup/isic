import random

import factory
import factory.django

from isic.core.models import Collection, Doi, Image, Segmentation, SegmentationReview
from isic.core.models.collection import CollectionShare
from isic.core.models.doi import DraftDoi
from isic.core.models.image import ImageShare
from isic.core.models.image_embedding import ImageEmbedding
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


class ImageEmbeddingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ImageEmbedding

    image = factory.SubFactory(ImageFactory)
    embedding = factory.LazyFunction(lambda: [random.uniform(-1, 1) for _ in range(3584)])


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


class CollectionShareFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CollectionShare

    grantor = factory.SubFactory(UserFactory)
    collection = factory.SubFactory(CollectionFactory, creator=factory.SelfAttribute("..grantor"))
    grantee = factory.SubFactory(UserFactory)


class ImageShareFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ImageShare

    grantor = factory.SubFactory(UserFactory)
    image = factory.SubFactory(ImageFactory)
    grantee = factory.SubFactory(UserFactory)


class SegmentationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Segmentation

    girder_id = factory.Faker("hexify", text="^" * 24)
    creator = factory.SubFactory(UserFactory)
    image = factory.SubFactory(ImageFactory)


class SegmentationReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SegmentationReview

    creator = factory.SubFactory(UserFactory)
    segmentation = factory.SubFactory(SegmentationFactory)
    approved = factory.Faker("boolean")
    skill = factory.Faker("random_element", elements=["novice", "expert"])
