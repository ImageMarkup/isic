from django.urls.base import reverse
import pytest

from isic.core.models.image import Image
import isic.core.tasks


# needs a real transaction due to setting the isolation level
@pytest.mark.django_db(transaction=True)
def test_image_list_metadata_download_view(mocker, staff_client, mailoutbox, user, image: Image):
    image.accession.update_metadata(
        user,
        {
            "age": 57,
            "lesion_id": "foo",
            "patient_id": "bar",
            "rcm_case_id": "baz",
            "diagnosis": "Melanoma Invasive",
            "image_type": "RCM: macroscopic",
        },
        ignore_image_check=True,
    )

    spy = mocker.spy(isic.core.tasks, "expiring_url")
    r = staff_client.get(reverse("core/image-list-metadata-download"), follow=True)
    assert r.status_code == 200

    assert len(mailoutbox) == 1
    assert spy.call_count == 1
    storage, key, _ = spy.call_args[0]
    actual = storage.open(key).read().decode()

    expected_headers = [
        "original_filename",
        "isic_id",
        "cohort_id",
        "cohort",
        "attribution",
        "copyright_license",
        "public",
        "age",
        "age_approx",
        "diagnosis_1",
        "diagnosis_2",
        "diagnosis_3",
        "image_type",
        "private_lesion_id",
        "lesion_id",
        "private_patient_id",
        "patient_id",
        "private_rcm_case_id",
        "rcm_case_id",
    ]

    # we know these can't be None due to the update_metadata call above
    assert image.accession.lesion
    assert image.accession.patient

    expected_row_items = [
        image.accession.original_blob_name,
        image.isic_id,
        image.accession.cohort_id,
        image.accession.cohort.name,
        image.accession.attribution,
        image.accession.copyright_license,
        image.public,
        "57",
        "55",
        "Malignant",
        "Malignant melanocytic proliferations (Melanoma)",
        "Melanoma Invasive",
        "RCM: macroscopic",
        "foo",
        image.accession.lesion_id,
        "bar",
        image.accession.patient_id,
        "baz",
        image.accession.rcm_case_id,
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
