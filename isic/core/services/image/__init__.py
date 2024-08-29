import itertools

from cachalot.api import cachalot_disabled
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet

from isic.core.models import Image, IsicId
from isic.ingest.models.accession import Accession


def image_create(*, creator: User, accession: Accession, public: bool) -> Image:
    with transaction.atomic():
        isic_id = IsicId.objects.create_random()
        image = Image(isic=isic_id, creator=creator, accession=accession, public=public)
        image.full_clean()
        image.save()
        return image


def image_share(
    *, qs: QuerySet[Image] | None = None, image: Image | None = None, grantor: User, grantee: User
) -> None:
    # is not None is necessary because qs could be an empty queryset
    if qs is not None and image is not None:
        raise ValueError("qs and image are mutually exclusive arguments.")

    if qs is None and image is None:
        raise ValueError("Either qs or image must be provided.")

    if image:
        qs = Image.objects.filter(pk=image.pk)

    with transaction.atomic(), cachalot_disabled():
        ImageShareM2M = Image.shares.through  # noqa: N806
        for image_batch in itertools.batched(qs.iterator(), 5_000):
            # ignore_conflicts is necessary to make this method idempotent. ignore_conflicts only
            # ignores primary key, duplicate, and exclusion constraints. we don't use primary
            # key or exclusion here, so this should only ignore duplicate entries.
            ImageShareM2M.objects.bulk_create(
                [
                    ImageShareM2M(image=image, grantor=grantor, grantee=grantee)
                    for image in image_batch
                ],
                ignore_conflicts=True,
            )
