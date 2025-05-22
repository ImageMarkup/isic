from django.core.files.storage import storages
import pytest

from isic.ingest.services.publish import unembargo_image


@pytest.mark.django_db(transaction=True)
def test_unembargo_images(image_factory):
    image = image_factory(public=False)
    blob_location = image.blob.name
    unembargo_image(image=image)
    image.refresh_from_db()
    assert image.public
    assert not storages["default"].exists(blob_location)
    assert storages["sponsored"].exists(image.blob.name)
