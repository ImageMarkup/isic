from django.urls.base import reverse
import pytest

from isic.core.models.image import Image


# needs a real transaction due to setting the isolation level
@pytest.mark.django_db(transaction=True)
def test_image_list_metadata_download_view(staff_client, user, image: Image):
    image.accession.update_metadata(
        user,
        {"age": 57, "lesion_id": "foo", "patient_id": "bar", "diagnosis": "melanoma"},
        ignore_image_check=True,
    )
    r = staff_client.get(reverse("core/image-list-metadata-download"))
    assert r.status_code == 200
    actual = r.getvalue().decode("utf-8")

    expected_headers = [
        "original_filename",
        "isic_id",
        "cohort_id",
        "cohort",
        "attribution",
        "copyright_license",
        "public",
        "age_approx",
        "age",
        "diagnosis",
        "private_lesion_id",
        "lesion_id",
        "private_patient_id",
        "patient_id",
    ]

    # we know these can't be None due to the update_metadata call above
    assert image.accession.lesion
    assert image.accession.patient

    expected_row_items = [
        image.accession.original_blob_name,
        image.isic_id,
        image.accession.cohort_id,
        image.accession.cohort.name,
        image.accession.cohort.attribution,
        image.accession.copyright_license,
        image.public,
        "55",
        "57",
        "melanoma",
        "foo",
        image.accession.lesion_id,
        "bar",
        image.accession.patient_id,
    ]

    expected = (
        "\r\n".join(
            [
                ",".join(expected_headers),
                ",".join([str(item) for item in expected_row_items]),
            ]
        )
        + "\r\n"
    )

    assert actual == expected
