from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls.base import reverse
import pytest


@pytest.mark.django_db
def test_upload_zip(
    cohort_factory, user, authenticated_client, zip_stream_only_images, eager_celery
):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    zip_stream_only_images.seek(0)
    zipfile = SimpleUploadedFile(
        'foo.zip',
        zip_stream_only_images.getvalue(),
        'application/zip',
    )

    authenticated_client.post(
        reverse('upload/zip', args=[cohort.pk]),
        {
            'blob': zipfile,
        },
    )

    assert cohort.accessions.count() == 5
