import pytest

from isic.core.models.image import Image
from isic.ingest.services.publish import unembargo_images


@pytest.mark.django_db
def test_unembargo_images(image_factory):
    image = image_factory(public=False)
    unembargo_images(qs=Image.objects.filter(id=image.id))
    image.refresh_from_db()
    assert image.public
