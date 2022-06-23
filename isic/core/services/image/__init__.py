from django.contrib.auth.models import User

from isic.core.models.image import Image
from isic.ingest.models.accession import Accession


def image_create(*, creator: User, accession: Accession, public: bool) -> Image:
    image = Image(creator=creator, accession=accession, public=public)
    image.full_clean()
    image.save()
    return image
