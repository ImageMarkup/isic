from typing import Optional

from django.urls.base import reverse

from isic.ingest.models import Cohort

from .metadata import *  # noqa


def make_breadcrumbs(cohort: Optional[Cohort] = None) -> list:
    ret = [[reverse('ingest-review'), 'Ingest Review']]

    if cohort:
        ret.append([reverse('cohort-detail', args=[cohort.pk]), cohort.name])

    return ret
