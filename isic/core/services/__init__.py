from typing import Iterator

from django.db.models import Func
from django.db.models.query import QuerySet

from isic.core.models.image import Image
from isic.ingest.models.accession import Accession


class JsonKeys(Func):
    function = 'jsonb_object_keys'


def _image_metadata_csv_headers(*, qs: QuerySet[Image]) -> list[str]:
    headers = ['isic_id', 'attribution', 'copyright_license']

    # depending on which queryset is passed in, the set of headers is different.
    # get the superset of headers for this particular queryset.
    used_metadata_keys = list(
        Accession.objects.filter(image__in=qs)
        .annotate(metadata_keys=JsonKeys('metadata'))
        .order_by()
        .values_list('metadata_keys', flat=True)
        .distinct()
    )

    # TODO: this is a very leaky part of RESTRICTED_METADATA_FIELDS that
    # should be refactored.
    if 'age' in used_metadata_keys:
        used_metadata_keys.append('age_approx')
        used_metadata_keys.remove('age')

    return headers + sorted(used_metadata_keys)


def image_metadata_csv_rows(*, qs: QuerySet[Image]) -> Iterator[dict]:
    for image in qs.order_by('isic_id').values(
        'isic_id',
        'accession__cohort__attribution',
        'accession__cohort__copyright_license',
        'accession__metadata',
    ):
        yield {
            **{
                'isic_id': image['isic_id'],
                'attribution': image['accession__cohort__attribution'],
                'copyright_license': image['accession__cohort__copyright_license'],
                **Accession._redact_metadata(image['accession__metadata']),
            }
        }
