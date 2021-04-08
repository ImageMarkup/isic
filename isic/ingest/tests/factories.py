import pathlib

import factory
import factory.django

from isic.factories import UserFactory
from isic.ingest.models import Accession, Cohort, Contributor, CopyrightLicense, MetadataFile, Zip

from .csv_streams import csv_stream_without_filename_column
from .zip_streams import zip_stream_only_images

data_dir = pathlib.Path(__file__).parent / 'data'


class ContributorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contributor

    creator = factory.SubFactory(UserFactory)
    institution_url = factory.Faker('url')
    legal_contact_info = factory.Faker('address')


class CohortFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cohort

    contributor = factory.SubFactory(ContributorFactory)
    creator = factory.SelfAttribute('contributor.creator')
    name = factory.Faker('sentence', nb_words=3, variable_nb_words=True)
    description = factory.Faker('paragraph')
    copyright_license = CopyrightLicense.CC_BY
    attribution = factory.Faker('paragraph')


class MetadataFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MetadataFile

    cohort = factory.SubFactory(CohortFactory)
    creator = factory.SelfAttribute('cohort.creator')
    blob = factory.django.FileField(
        from_func=csv_stream_without_filename_column,
        filename=factory.Faker('file_name', extension='csv'),
    )
    blob_name = factory.SelfAttribute('blob.name')
    blob_size = factory.SelfAttribute('blob.size')


class ZipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Zip

    cohort = factory.SubFactory(CohortFactory)
    creator = factory.SelfAttribute('cohort.creator')
    blob = factory.django.FileField(
        from_func=zip_stream_only_images,
        filename=factory.Faker('file_name', extension='zip'),
    )
    blob_name = factory.SelfAttribute('blob.name')
    blob_size = factory.SelfAttribute('blob.size')


class AccessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Accession

    upload = factory.SubFactory(ZipFactory)
    original_blob = factory.django.FileField(from_path=data_dir / 'ISIC_0000000.jpg')
    blob_name = factory.SelfAttribute('original_blob.name')
