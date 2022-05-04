import sys

from django.core.exceptions import ValidationError
import djclick as click

from isic.ingest.models.cohort import Cohort
from isic.ingest.services.cohort import cohort_merge


@click.command()
@click.argument('cohort_id', nargs=-1, type=click.INT)
def merge_cohorts(cohort_id):
    assert len(cohort_id) > 1
    cohorts = []
    for id_ in cohort_id:
        cohorts.append(Cohort.objects.get(pk=id_))

    try:
        cohort_merge(dest_cohort=cohorts[0], other_cohorts=cohorts[1:])
    except ValidationError as e:
        click.secho(e.message, color='red', err=True)
        sys.exit(1)
    else:
        click.secho(f'Merged {len(cohorts[1:])} cohorts into {cohorts[0].name}.', color='green')
