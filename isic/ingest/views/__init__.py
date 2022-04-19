from django.urls.base import reverse

from isic.ingest.models.cohort import Cohort


def make_breadcrumbs(cohort: Cohort | None = None) -> list:
    ret = [[reverse('ingest-review'), 'Ingest Review']]

    if cohort:
        ret.append([reverse('cohort-detail', args=[cohort.pk]), cohort.name])

    return ret
