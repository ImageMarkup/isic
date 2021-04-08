from typing import List, Optional

from django.urls.base import reverse

from isic.ingest.models import Cohort

from .metadata import *  # noqa


def make_breadcrumbs(cohort: Optional[Cohort] = None) -> List:
    ret = [[reverse('ingest-review'), 'Ingest Review']]

    if cohort:
        ret.append([reverse('cohort-detail', args=[cohort.pk]), cohort.name])

    return ret


def staff_or_creator_filter(user):
    if user.is_staff:
        return {}
    else:
        return {'creator': user}
