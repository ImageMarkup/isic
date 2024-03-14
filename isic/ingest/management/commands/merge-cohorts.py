import sys

from django.core.exceptions import ValidationError
import djclick as click

from isic.ingest.models.cohort import Cohort
from isic.ingest.services.cohort import cohort_merge


@click.command()
@click.argument("cohort_id", nargs=-1, type=click.INT)
def merge_cohorts(cohort_id):
    if len(cohort_id) < 2:
        click.secho("Must provide at least 2 cohort IDs to merge.", color="red", err=True)
        sys.exit(1)

    cohorts = [Cohort.objects.get(pk=id_) for id_ in cohort_id]

    try:
        cohort_merge(dest_cohort=cohorts[0], other_cohorts=cohorts[1:])
    except ValidationError as e:
        click.secho(e.message, color="red", err=True)
        sys.exit(1)
    else:
        click.secho(f"Merged {len(cohorts[1:])} cohorts into {cohorts[0].name}.", color="green")
