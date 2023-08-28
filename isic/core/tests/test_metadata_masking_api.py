import pytest

from isic.core.models.image import Image
from isic.core.services import image_metadata_csv_headers, image_metadata_csv_rows


@pytest.fixture
def image_with_maskable_metadata(image):
    image.accession.update_metadata(
        image.creator,
        {
            "age": 32,
            "lesion_id": "supersecretlesionid",
        },
        ignore_image_check=True,
    )
    return image


@pytest.mark.django_db
def test_accession_exposes_unsafe_metadata(image_with_maskable_metadata):
    assert image_with_maskable_metadata.accession.metadata["age"] == 32
    assert "age_approx" not in image_with_maskable_metadata.accession.metadata
    assert "lesion_id" not in image_with_maskable_metadata.accession.metadata


@pytest.mark.django_db
def test_image_exposes_safe_metadata(image_with_maskable_metadata):
    assert image_with_maskable_metadata.metadata["age_approx"] == 30
    assert "age" not in image_with_maskable_metadata.metadata
    assert image_with_maskable_metadata.metadata["lesion_id"] != "supersecretlesionid"


@pytest.mark.django_db
def test_image_csv_headers_exposes_safe_metadata(image_with_maskable_metadata):
    headers = image_metadata_csv_headers(qs=Image.objects.all())
    assert "age" not in headers
    assert "age_approx" in headers
    assert "lesion_id" in headers


@pytest.mark.django_db
def test_image_csv_rows_exposes_safe_metadata(image_with_maskable_metadata):
    rows = image_metadata_csv_rows(qs=Image.objects.all())
    for row in rows:
        assert "age" not in row
        assert "age_approx" in row
        assert "lesion_id" in row
        assert row["lesion_id"] != "supersecretlesionid"
