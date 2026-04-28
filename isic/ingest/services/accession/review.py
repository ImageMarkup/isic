from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from isic.ingest.models.accession import Accession
from isic.ingest.models.accession_review import AccessionReview


def update_or_create_accession_review(
    *, accession: Accession, reviewer: User, reviewed_at: datetime, value: bool
) -> AccessionReview:
    if accession.published:
        raise ValidationError("Cannot review an accession after publish.")

    accession_review, _ = AccessionReview.objects.update_or_create(
        accession=accession,
        defaults={
            "creator": reviewer,
            "reviewed_at": reviewed_at,
            "value": value,
        },
    )

    return accession_review


def bulk_create_accession_reviews(*, reviewer: User, accession_ids_values: dict[int, bool]):
    accession_reviews = []
    reviewed_at = timezone.now()

    with transaction.atomic():
        for accession in (
            Accession.objects.select_related("image")
            .filter(pk__in=accession_ids_values.keys())
            .select_for_update(of=("self",))
        ):
            if accession.published:
                raise ValidationError("Cannot review an accession after publish.")

            accession_reviews.append(
                AccessionReview(
                    accession=accession,
                    creator=reviewer,
                    reviewed_at=reviewed_at,
                    value=accession_ids_values[accession.pk],
                )
            )

        AccessionReview.objects.bulk_create(accession_reviews)


def delete_accession_review(*, accession: Accession):
    if hasattr(accession, "review"):
        accession.review.delete()
