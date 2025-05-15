import itertools

from django.contrib.auth.models import User
from django.core.files import File
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

        if public:
            accession.public_blob_name = f"{image.isic_id}.{image.extension}"
            accession.public_blob = File(accession.blob, name=accession.public_blob_name)
            accession.public_blob_size = accession.blob_size
            accession.save()

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

    assert qs is not None  # noqa: S101

    with transaction.atomic():
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
