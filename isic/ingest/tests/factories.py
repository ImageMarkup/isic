import pathlib

import factory
import factory.django
from faker import Faker
from faker.providers.python import Provider

from isic.core.models import CopyrightLicense
from isic.factories import UserFactory
from isic.ingest.models import Accession, Cohort, Contributor, MetadataFile, ZipUpload
from isic.ingest.validators import (
    BenignMalignantEnum,
    ColorTintEnum,
    DermoscopicTypeEnum,
    DiagnosisConfirmTypeEnum,
    DiagnosisEnum,
    GeneralAnatomicSiteEnum,
    ImageTypeEnum,
    MelClassEnum,
    MelMitoticIndexEnum,
    MelTypeEnum,
    NevusTypeEnum,
)

from .csv_streams import csv_stream_without_filename_column
from .zip_streams import zip_stream_only_images

data_dir = pathlib.Path(__file__).parent / 'data'

fake = Faker()


class ContributorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Contributor

    institution_name = factory.Faker('sentence', nb_words=5, variable_nb_words=True)
    institution_url = factory.Faker('url')
    legal_contact_info = factory.Faker('address')
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
    creator = factory.SelfAttribute('contributor.creator')
    name = factory.Faker('sentence', nb_words=3, variable_nb_words=True)
    description = factory.Faker('paragraph')
    copyright_license = CopyrightLicense.CC_BY
    attribution = factory.Faker('sentence')


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


class ZipUploadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ZipUpload

    cohort = factory.SubFactory(CohortFactory)
    creator = factory.SelfAttribute('cohort.creator')
    blob = factory.django.FileField(
        from_func=zip_stream_only_images,
        filename=factory.Faker('file_name', extension='zip'),
    )
    blob_name = factory.SelfAttribute('blob.name')
    blob_size = factory.SelfAttribute('blob.size')


def accession_metadata():
    def from_enum(e):
        return fake.random_element([x.value for x in e])

    m = {
        'age': fake.pyint(1, 85),
        'sex': fake.random_element(['male', 'female']),
        'benign_malignant': from_enum(BenignMalignantEnum),
        'diagnosis': from_enum(DiagnosisEnum),
        'diagnosis_confirm_type': from_enum(DiagnosisConfirmTypeEnum),
        'personal_hx_mm': fake.boolean(),
        'family_hx_mm': fake.boolean(),
        'clin_size_long_diam_mm': fake.pyfloat(
            left_digits=3, right_digits=2, positive=True, max_value=100.0
        ),
        'melanocytic': fake.boolean(),
        'patient_id': f'IP_{fake.pyint(1_000_000,9_999_999)}',
        'lesion_id': f'IL_{fake.pyint(1_000_000,9_999_999)}',
        'acquisition_day': fake.pyint(),
        'marker_pen': fake.boolean(),
        'hairy': fake.boolean(),
        'blurry': fake.boolean(),
        'nevus_type': from_enum(NevusTypeEnum),
        'image_type': from_enum(ImageTypeEnum),
        'dermoscopic_type': from_enum(DermoscopicTypeEnum),
        'anatom_site_general': from_enum(GeneralAnatomicSiteEnum),
        'color_tint': from_enum(ColorTintEnum),
        'mel_class': from_enum(MelClassEnum),
        'mel_mitotic_index': from_enum(MelMitoticIndexEnum),
        'mel_thick_mm': fake.pyfloat(left_digits=1, right_digits=2, positive=True, max_value=5.0),
        'mel_type': from_enum(MelTypeEnum),
        'mel_ulcer': fake.boolean(),
    }

    for key in fake.random.sample(list(m.keys()), fake.pyint(0, len(m))):
        del m[key]

    return m


def accession_unstructured_metadata():
    return fake.pydict(
        value_types=list(set(Provider.default_value_types) - {'date_time', 'decimal'})
    )


class AccessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Accession

    zip_upload = factory.SubFactory(ZipUploadFactory)
    cohort = factory.SelfAttribute('zip_upload.cohort')
    original_blob = factory.django.FileField(from_path=data_dir / 'ISIC_0000000.jpg')
    blob = factory.django.FileField(from_path=data_dir / 'ISIC_0000000.jpg')
    blob_name = factory.SelfAttribute('original_blob.name')
    thumbnail_256 = factory.django.FileField(from_path=data_dir / 'ISIC_0000000_thumbnail_256.jpg')

    quality_check = factory.Faker('boolean')
    diagnosis_check = factory.Faker('boolean')
    phi_check = factory.Faker('boolean')
    duplicate_check = factory.Faker('boolean')
    lesion_check = factory.Faker('boolean')

    metadata = factory.LazyFunction(accession_metadata)
    unstructured_metadata = factory.LazyFunction(accession_unstructured_metadata)
