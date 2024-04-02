import pytest

from isic.core.models.image import Image
from isic.core.services import image_metadata_csv, staff_image_metadata_csv


@pytest.fixture()
def image_with_metadata(image):
    image.accession.copyright_license = "CC-0"
    image.accession.save()

    image.accession.update_metadata(
        image.creator,
        {
            "age": 32,
            "benign_malignant": "benign",
            "diagnosis": "nevus",
            "patient_id": "supersecretpatientid",
            "lesion_id": "supersecretlesionid",
            "unstructuredfield": "foo",
        },
        ignore_image_check=True,
    )
    return image


@pytest.mark.django_db()
def test_image_metadata_csv_rows_correct(image_with_metadata):
    rows = image_metadata_csv(qs=Image.objects.filter(pk=image_with_metadata.pk))
    next(rows)
    row = next(rows)
    assert row == {
        "age_approx": image_with_metadata.accession.age_approx,
        "attribution": image_with_metadata.accession.cohort.attribution,
        "benign_malignant": image_with_metadata.accession.benign_malignant,
        "copyright_license": image_with_metadata.accession.copyright_license,
        "diagnosis": image_with_metadata.accession.diagnosis,
        "isic_id": image_with_metadata.isic_id,
        "lesion_id": image_with_metadata.accession.lesion_id,
        "patient_id": image_with_metadata.accession.patient_id,
    }


@pytest.mark.django_db()
def test_staff_image_metadata_csv_rows_correct(image_with_metadata):
    rows = staff_image_metadata_csv(qs=Image.objects.filter(pk=image_with_metadata.pk))
    next(rows)
    row = next(rows)
    assert row == {
        "age_approx": image_with_metadata.accession.age_approx,
        "age": image_with_metadata.accession.age,
        "attribution": image_with_metadata.accession.cohort.attribution,
        "benign_malignant": image_with_metadata.accession.benign_malignant,
        "cohort_id": image_with_metadata.accession.cohort_id,
        "cohort": image_with_metadata.accession.cohort.name,
        "copyright_license": image_with_metadata.accession.copyright_license,
        "diagnosis": image_with_metadata.accession.diagnosis,
        "isic_id": image_with_metadata.isic_id,
        "lesion_id": image_with_metadata.accession.lesion_id,
        "original_filename": image_with_metadata.accession.original_blob_name,
        "patient_id": image_with_metadata.accession.patient_id,
        "private_lesion_id": image_with_metadata.accession.lesion.private_lesion_id,
        "private_patient_id": image_with_metadata.accession.patient.private_patient_id,
        "public": image_with_metadata.public,
        "unstructured.unstructuredfield": "foo",
    }
