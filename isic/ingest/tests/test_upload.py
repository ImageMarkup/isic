import io
import pathlib
from typing import BinaryIO
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf

from isic.ingest.models.accession import AccessionStatus

data_dir = pathlib.Path(__file__).parent / "data"


@pytest.fixture
def zip_stream_garbage() -> BinaryIO:
    file_stream = io.BytesIO()

    with zipfile.ZipFile(file_stream, mode="w") as zip_file:
        # real files
        zip_file.write(data_dir / "ISIC_0000000.jpg")
        zip_file.write(data_dir / "ISIC_0000001.jpg")
        zip_file.write(data_dir / "ISIC_0000002.jpg")
        zip_file.write(data_dir / "ISIC_0000003.jpg")
        zip_file.write(data_dir / "ISIC_0000004.jpg")

        # skippable files
        zip_file.writestr("subdir/._foobar", data=b"1234")
        zip_file.writestr("Thumbs.db", data=b"1234")
        zip_file.writestr("somefile.jpg", data=b"")

        # appear to be real but are skippable
        zip_file.writestr("notanimage.jpg", data=b"1234")
        zip_file.writestr("spreadsheet.csv", data=b"foo,bar,baz\n1,2,3")

    return file_stream


@pytest.mark.parametrize(
    "zip_stream",
    [
        lf("zip_stream_only_images"),
        lf("zip_stream_garbage"),
    ],
)
@pytest.mark.django_db
def test_upload_zip(
    cohort_factory,
    user,
    authenticated_client,
    zip_stream,
    django_capture_on_commit_callbacks,
):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    zip_stream.seek(0)
    zipfile = SimpleUploadedFile(
        "foo.zip",
        zip_stream.getvalue(),
        "application/zip",
    )

    with django_capture_on_commit_callbacks(execute=True):
        authenticated_client.post(
            reverse("upload/zip", args=[cohort.pk]),
            {
                "blob": zipfile,
            },
        )

    assert cohort.accessions.filter(status=AccessionStatus.SUCCEEDED).count() == 5
