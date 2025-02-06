import pytest

from isic.core.models.image import Image
from isic.core.services import image_metadata_csv


@pytest.fixture
def image_with_maskable_metadata(image):
    image.accession.update_metadata(
        image.creator,
        {
            "age": 32,
            "lesion_id": "supersecretlesionid",
            "patient_id": "supersecretpatientid",
        },
        ignore_image_check=True,
    )
    return image


@pytest.mark.django_db
def test_accession_exposes_unsafe_metadata(image_with_maskable_metadata):
    assert image_with_maskable_metadata.accession.metadata["age"] == 32
    assert "age_approx" not in image_with_maskable_metadata.accession.metadata
    assert "lesion_id" not in image_with_maskable_metadata.accession.metadata
    assert "patient_id" not in image_with_maskable_metadata.accession.metadata


@pytest.mark.django_db
def test_image_masks_unsafe_metadata(image_with_maskable_metadata):
    assert image_with_maskable_metadata.metadata["age_approx"] == 30
    assert "age" not in image_with_maskable_metadata.metadata
    assert image_with_maskable_metadata.metadata["lesion_id"] != "supersecretlesionid"
    assert image_with_maskable_metadata.metadata["patient_id"] != "supersecretpatientid"


@pytest.mark.django_db
def test_image_csv_headers_exposes_safe_metadata(image_with_maskable_metadata):
    headers = next(image_metadata_csv(qs=Image.objects.all()))
    assert "age" not in headers
    assert "age_approx" in headers
    assert "lesion_id" in headers
    assert "patient_id" in headers


@pytest.mark.django_db
def test_image_csv_rows_exposes_safe_metadata(image_with_maskable_metadata):
    rows = image_metadata_csv(qs=Image.objects.all())
    next(rows)
    for row in rows:
        assert isinstance(row, dict)
        assert "age" not in row
        assert "age_approx" in row
        assert "lesion_id" in row
        assert "patient_id" in row
        assert row["lesion_id"] != "supersecretlesionid"
        assert row["patient_id"] != "supersecretpatientid"
