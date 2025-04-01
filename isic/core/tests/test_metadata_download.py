import pytest

from isic.core.models.image import Image
from isic.core.services import image_metadata_csv, staff_image_metadata_csv
from isic.ingest.models.accession import Accession


@pytest.fixture
def image_with_metadata(image):
    image.accession.copyright_license = "CC-0"
    image.accession.save()

    image.accession.update_metadata(
        image.creator,
        {
            "age": 32,
            "diagnosis": "Nevus",
            "patient_id": "supersecretpatientid",
            "lesion_id": "supersecretlesionid",
            "rcm_case_id": "supersecretrcmcaseid",
            "image_type": "RCM: macroscopic",
            "unstructuredfield": "foo",
        },
        ignore_image_check=True,
    )

    # TODO: transition code that should be removed when iddx/legacy_dx stuff is removed
    Accession.objects.filter(id=image.accession.id).update(legacy_dx="nevus")

    return image


@pytest.mark.django_db
def test_image_metadata_csv_rows_correct(image_with_metadata):
    rows = image_metadata_csv(qs=Image.objects.filter(pk=image_with_metadata.pk))
    next(rows)
    row = next(rows)
    assert row == {
        "age_approx": image_with_metadata.accession.age_approx,
        "attribution": image_with_metadata.accession.cohort.default_attribution,
        "copyright_license": image_with_metadata.accession.copyright_license,
        "diagnosis": "nevus",
        "diagnosis_1": "Benign",
        "diagnosis_2": "Benign melanocytic proliferations",
        "diagnosis_3": "Nevus",
        "image_type": image_with_metadata.accession.image_type,
        "isic_id": image_with_metadata.isic_id,
        "lesion_id": image_with_metadata.accession.lesion_id,
        "patient_id": image_with_metadata.accession.patient_id,
        "rcm_case_id": image_with_metadata.accession.rcm_case_id,
    }


@pytest.mark.django_db
def test_staff_image_metadata_csv_rows_correct(image_with_metadata):
    rows = staff_image_metadata_csv(qs=Image.objects.filter(pk=image_with_metadata.pk))
    next(rows)
    row = next(rows)
    assert row == {
        "age_approx": image_with_metadata.accession.age_approx,
        "age": image_with_metadata.accession.age,
        "attribution": image_with_metadata.accession.cohort.default_attribution,
        "cohort_id": image_with_metadata.accession.cohort_id,
        "cohort": image_with_metadata.accession.cohort.name,
        "copyright_license": image_with_metadata.accession.copyright_license,
        "diagnosis": "nevus",
        "diagnosis_1": "Benign",
        "diagnosis_2": "Benign melanocytic proliferations",
        "diagnosis_3": "Nevus",
        "image_type": image_with_metadata.accession.image_type,
        "isic_id": image_with_metadata.isic_id,
        "original_filename": image_with_metadata.accession.original_blob_name,
        "lesion_id": image_with_metadata.accession.lesion_id,
        "patient_id": image_with_metadata.accession.patient_id,
        "rcm_case_id": image_with_metadata.accession.rcm_case_id,
        "private_lesion_id": image_with_metadata.accession.lesion.private_lesion_id,
        "private_patient_id": image_with_metadata.accession.patient.private_patient_id,
        "private_rcm_case_id": image_with_metadata.accession.rcm_case.private_rcm_case_id,
        "public": image_with_metadata.public,
        "unstructured.unstructuredfield": "foo",
    }
