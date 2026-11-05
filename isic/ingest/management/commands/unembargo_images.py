import csv

from django.db import transaction
import djclick as click

from isic.core.models import Image
from isic.ingest.services.publish import unembargo_image


@click.command(help="Unembargo the images listed in a CSV with an isic_id column")
@click.argument("csv_file", type=click.File())
def unembargo_images(csv_file):
    isic_ids = {row["isic_id"] for row in csv.DictReader(csv_file)}
    images = Image.objects.filter(isic_id__in=isic_ids).select_related("accession")

    if images.count() != len(isic_ids):
        raise click.ClickException(
            f"{len(isic_ids)} isic ids in the CSV but {images.count()} images found."
        )

    private_images = images.private()
    already_public = images.count() - private_images.count()
    if already_public:
        click.echo(f"Skipping {already_public} already public images.")

    with click.progressbar(
        private_images.iterator(), length=private_images.count(), show_pos=True
    ) as bar:
        for image in bar:
            with transaction.atomic():
                unembargo_image(image=image)
