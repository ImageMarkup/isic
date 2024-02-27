import pathlib

import factory
import factory.django

from isic.core.models import CopyrightLicense
from isic.factories import UserFactory
from isic.ingest.models import Accession, Cohort, Contributor, Lesion, MetadataFile, ZipUpload
from isic.ingest.models.accession_review import AccessionReview

from .csv_streams import csv_stream_without_filename_column
from .zip_streams import zip_stream_only_images

data_dir = pathlib.Path(__file__).parent / "data"


class ContributorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contributor

    institution_name = factory.Faker("sentence", nb_words=5, variable_nb_words=True)
    institution_url = factory.Faker("url")
    legal_contact_info = factory.Faker("address")
    creator = factory.SubFactory(UserFactory)

    @factory.post_generation
    def owners(self, create, extracted, **kwargs):
        owners = [self.creator] if extracted is None else extracted
        for owner in owners:
            self.owners.add(owner)


class CohortFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cohort

    contributor = factory.SubFactory(ContributorFactory)
    creator = factory.SelfAttribute("contributor.creator")
    name = factory.Faker("sentence", nb_words=3, variable_nb_words=True)
    description = factory.Faker("paragraph")
    default_copyright_license = factory.Faker(
        "random_element", elements=[e[0] for e in CopyrightLicense.choices]
    )
    attribution = factory.Faker("sentence")


class MetadataFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MetadataFile

    cohort = factory.SubFactory(CohortFactory)
    creator = factory.SelfAttribute("cohort.creator")
    blob = factory.django.FileField(
        from_func=csv_stream_without_filename_column,
        filename=factory.Faker("file_name", extension="csv"),
    )
    blob_name = factory.SelfAttribute("blob.name")
    blob_size = factory.SelfAttribute("blob.size")


class ZipUploadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ZipUpload

    cohort = factory.SubFactory(CohortFactory)
    creator = factory.SelfAttribute("cohort.creator")
    blob = factory.django.FileField(
        from_func=zip_stream_only_images,
        filename=factory.Faker("file_name", extension="zip"),
    )
    blob_name = factory.SelfAttribute("blob.name")
    blob_size = factory.SelfAttribute("blob.size")


class AccessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Accession

    creator = factory.SelfAttribute("cohort.creator")
    zip_upload = factory.SubFactory(ZipUploadFactory)
    cohort = factory.SelfAttribute("zip_upload.cohort")
    original_blob = factory.django.FileField(
        from_path=data_dir / "ISIC_0000000.jpg",
        filename=factory.Sequence(lambda n: f"ISIC_{n:07}.jpg"),
    )
    original_blob_name = factory.SelfAttribute("original_blob.name")
    original_blob_size = factory.SelfAttribute("original_blob.size")
    blob = factory.django.FileField(
        from_path=data_dir / "ISIC_0000000.jpg",
        filename=factory.Sequence(lambda n: f"ISIC_{n:07}.jpg"),
    )
    blob_name = factory.Faker("uuid4")
    blob_size = factory.SelfAttribute("blob.size")
    thumbnail_256 = factory.django.FileField(from_path=data_dir / "ISIC_0000000_thumbnail_256.jpg")
    thumbnail_256_size = factory.SelfAttribute("thumbnail_256.size")
    copyright_license = factory.Faker(
        "random_element", elements=[e[0] for e in CopyrightLicense.choices]
    )

    # Using "metadata = factory.Dict" breaks pytest-factoryboy; see
    # https://github.com/pytest-dev/pytest-factoryboy/issues/67


class AccessionReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccessionReview

    creator = factory.SubFactory(UserFactory)
    accession = factory.SubFactory(AccessionFactory)
    reviewed_at = factory.Faker("date_time", tzinfo=factory.Faker("pytimezone"))
    value = factory.Faker("boolean")


class LesionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Lesion

    id = factory.Sequence(lambda n: f"IL_{n:07}")
    cohort = factory.SubFactory(CohortFactory)
    private_lesion_id = factory.Faker("uuid4")
