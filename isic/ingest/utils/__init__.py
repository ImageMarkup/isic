from typing import Optional

from django.urls.base import reverse

from isic.ingest.models import Cohort

from .metadata import *  # noqa


def make_breadcrumbs(cohort: Optional[Cohort] = None) -> list:
    ret = [[reverse('ingest-review'), 'Ingest Review']]

    if cohort:
        ret.append([reverse('cohort-detail', args=[cohort.pk]), cohort.name])

    return ret


def staff_or_owner_filter(user, creator_field='owner'):
    if user.is_staff:
        return {}
    else:
        return {creator_field: user}
