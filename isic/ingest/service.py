from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import File

from isic.ingest.models.accession import Accession
from isic.ingest.models.accession_review import AccessionReview
from isic.ingest.models.cohort import Cohort
from isic.ingest.tasks import accession_generate_blob_task


def accession_create(
    *, creator: User, cohort: Cohort, original_blob: File, blob_name: str
) -> Accession:
    # TODO: should the user this is acting on behalf of be the same as the creator?
    if not creator.has_perm('ingest.add_accession', cohort):
        raise ValidationError('You do not have permission to add an image to this cohort.')

    if cohort.accessions.filter(blob_name=blob_name).exists():
        raise ValidationError('An accession with this name already exists.')

    accession = Accession.objects.create(
        creator=creator, cohort=cohort, original_blob=original_blob, blob_name=blob_name
    )

    accession_generate_blob_task.delay(accession.pk)

    return accession


def accession_review_update_or_create(
    *, accession: Accession, reviewer: User, reviewed_at: datetime, value: bool
) -> AccessionReview:
    assert not accession.published, 'Cannot review an accession after publish.'

    accession_review, _ = AccessionReview.objects.update_or_create(
        accession=accession,
        defaults={
            'creator': reviewer,
            'reviewed_at': reviewed_at,
            'value': value,
        },
    )

    return accession_review


def accession_review_bulk_create(*, accession_reviews: list[AccessionReview]):
    for accession_review in accession_reviews:
        assert not accession_review.accession.published, 'Cannot review an accession after publish.'

    AccessionReview.objects.bulk_create(accession_reviews)


def accession_review_delete(*, accession: Accession):
    if hasattr(accession, 'review'):
        accession.review.delete()
