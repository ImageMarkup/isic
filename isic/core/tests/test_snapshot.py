import zipfile

from django.core.files.storage import storages
import pytest

from isic.core.tasks import generate_archive_snapshot_task


@pytest.mark.django_db(transaction=True)
def test_snapshot_task(public_image, private_image):
    generate_archive_snapshot_task()

    assert storages["sponsored"].exists("snapshots/ISIC_images.zip")

    with (
        storages["sponsored"].open("snapshots/ISIC_images.zip", "rb") as f,
        zipfile.ZipFile(f) as z,
    ):
        assert f"images/{public_image.isic_id}.jpg" in z.namelist()
        assert f"images/{private_image.isic_id}.jpg" not in z.namelist()

    # clean this up since it's in a predetermined spot and it's useful to sometimes run
    # tests via pytest-repeat.
    storages["sponsored"].delete("snapshots/ISIC_images.zip")
