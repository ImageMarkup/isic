import datetime
import pathlib
from typing import Any

import factory
import factory.django
from isic_metadata.fields import DiagnosisEnum

from isic.core.models import CopyrightLicense
from isic.factories import UserFactory
from isic.ingest.models import (
    Accession,
    Cohort,
    Contributor,
    Lesion,
    MetadataFile,
    UnstructuredMetadata,
    ZipUpload,
)
from isic.ingest.models.accession import AccessionStatus
from isic.ingest.models.accession_review import AccessionReview

from .csv_streams import csv_stream_without_filename_column
from .zip_streams import zip_stream_only_images

data_dir = pathlib.Path(__file__).parent / "data"


class ContributorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contributor
        skip_postgeneration_save = True

    institution_name = factory.Faker("sentence", nb_words=5, variable_nb_words=True)
    institution_url = factory.Faker("url")
    legal_contact_info = factory.Faker("address")
    creator = factory.SubFactory(UserFactory)

    @factory.post_generation
    def owners(self, create: bool, extracted: Any, **kwargs: Any) -> None:  # noqa: FBT001
        if not create:
            return
        if extracted is None:
            # The creator is the default owner.
            extracted = [self.creator]
        self.owners.add(*extracted)


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
    default_attribution = factory.Faker("sentence")


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


class UnstructuredMetadataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UnstructuredMetadata

    accession = factory.SubFactory("isic.ingest.tests.factories.AccessionFactory")
    value = factory.LazyFunction(dict)


class AccessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Accession
        skip_postgeneration_save = True

    class Params:
        ingested = factory.Trait(
            status=AccessionStatus.SUCCEEDED,
            width=factory.Faker("random_int", min=1, max=1000),
            height=factory.Faker("random_int", min=1, max=1000),
        )

        # these are all of the relevant fields that need to be set if an accession is related
        # to a public image.
        public = factory.Trait(
            blob="",
            thumbnail_256="",
            sponsored_blob=factory.django.FileField(
                from_path=data_dir / "ISIC_0000000.jpg",
                filename=factory.Sequence(lambda n: f"ISIC_{n:07}.jpg"),
            ),
            blob_size=factory.SelfAttribute("sponsored_blob.size"),
            sponsored_thumbnail_256_blob=factory.django.FileField(
                from_path=data_dir / "ISIC_0000000_thumbnail_256.jpg",
                filename=factory.Sequence(lambda n: f"ISIC_{n:07}_thumbnail_256.jpg"),
            ),
            thumbnail_256_size=factory.SelfAttribute("sponsored_thumbnail_256_blob.size"),
            ingested=True,
        )

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
    sponsored_blob = ""

    blob_size = factory.SelfAttribute("blob.size")

    thumbnail_256 = factory.django.FileField(
        from_path=data_dir / "ISIC_0000000_thumbnail_256.jpg",
    )

    sponsored_thumbnail_256_blob = ""

    thumbnail_256_size = factory.SelfAttribute("thumbnail_256.size")

    copyright_license = factory.Faker(
        "random_element", elements=[e[0] for e in CopyrightLicense.choices]
    )
    attribution = factory.Faker("random_element", elements=[factory.Faker("sentence"), ""])

    unstructured_metadata = factory.RelatedFactory(UnstructuredMetadataFactory, "accession")

    # Using "metadata = factory.Dict" breaks pytest-factoryboy; see
    # https://github.com/pytest-dev/pytest-factoryboy/issues/67

    @factory.post_generation
    def short_diagnosis(self, create: bool, extracted: Any, **kwargs: Any) -> None:  # noqa: FBT001
        if extracted is None:
            # Normal flow, no short_diagnosis provided.
            return

        if extracted == "melanoma":
            diagnosis = DiagnosisEnum.malignant_malignant_melanocytic_proliferations_melanoma_melanoma_invasive  # noqa: E501
        elif extracted == "nevus":
            diagnosis = DiagnosisEnum.benign_benign_melanocytic_proliferations_nevus_nevus_spitz
        else:
            raise ValueError(f"Unknown short_diagnosis: {extracted}")
        if kwargs:
            raise ValueError("Unknown additional arguments to short_diagnosis: {kwargs}")

        for key, value in DiagnosisEnum.as_dict(diagnosis).items():
            setattr(self, key, value)

        if create:
            self.save()


class AccessionReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccessionReview

    creator = factory.SubFactory(UserFactory)
    accession = factory.SubFactory(AccessionFactory)
    reviewed_at = factory.Faker("date_time", tzinfo=datetime.UTC)
    value = factory.Faker("boolean")


class LesionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Lesion

    id = factory.Sequence(lambda n: f"IL_{n:07}")
    cohort = factory.SubFactory(CohortFactory)
    private_lesion_id = factory.Faker("uuid4")
