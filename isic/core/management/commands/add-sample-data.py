from datetime import UTC, datetime
from pathlib import Path
import sys
import tempfile

from django.contrib.auth.models import User
from django.core.files import File
from django.db import transaction
import djclick as click
import requests

from isic.core.models import CopyrightLicense, Image, IsicId
from isic.core.services.iptc import embed_iptc_metadata_for_image
from isic.core.tasks import sync_elasticsearch_indices_task
from isic.core.utils.db import lock_table_for_writes
from isic.ingest.models import Accession, Cohort, Contributor
from isic.ingest.models.unstructured_metadata import UnstructuredMetadata
from isic.ingest.services.publish import unembargo_image

S3_BASE_URL = "https://isic-archive.s3.amazonaws.com/images/"


@click.command(help="Add sample data to the database")
@click.option("--n", default=50, help="Number of images to create")
def add_sample_data(n):
    user = get_or_create_sample_user()
    click.secho(f"Using user: {user.username}", fg="blue", err=True)

    contributor = get_or_create_sample_contributor(user)
    click.secho(f"Using contributor: {contributor.institution_name}", fg="blue", err=True)

    cohort_name = f"Specific Images Load {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"
    cohort = create_cohort(user, contributor, cohort_name)
    click.secho(f"Created cohort: {cohort.name} (ID: {cohort.pk})", fg="green", err=True)

    created_images = []
    skipped_images = []

    with click.progressbar(range(n), length=n, label="Creating images", file=sys.stderr) as bar:
        for i in bar:
            isic_id = f"ISIC_{i:07d}"

            if Image.objects.filter(isic_id=isic_id).exists():
                click.secho(f"\nSkipping {isic_id}: already exists", fg="yellow", err=True)
                skipped_images.append(isic_id)
                continue

            image_url = f"{S3_BASE_URL}{isic_id}.jpg"

            try:
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()
            except requests.RequestException as e:
                click.secho(f"\nFailed to download {isic_id}: {e}", fg="red", err=True)
                continue

            image_size = len(response.content)

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file.flush()

                with Path(temp_file.name).open("rb") as f:
                    image_file = File(f, name=f"{isic_id}.jpg")

                    with transaction.atomic():
                        accession = Accession(
                            creator=user,
                            cohort=cohort,
                            copyright_license=cohort.default_copyright_license,
                            original_blob=image_file,
                            original_blob_name=f"{isic_id}.jpg",
                            original_blob_size=image_size,
                        )
                        accession.unstructured_metadata = UnstructuredMetadata(accession=accession)
                        accession.full_clean(validate_constraints=False)
                        accession.save()
                        accession.unstructured_metadata.save()

            accession.generate_blob()
            accession.refresh_from_db()

            publish_image_with_specific_isic_id(
                accession=accession, isic_id=isic_id, publisher=user
            )

            created_images.append(isic_id)

    sync_elasticsearch_indices_task()

    click.secho("\nCreated images:", fg="green", err=True)
    for isic_id in created_images:
        click.echo(isic_id)

    if skipped_images:
        click.secho(f"\nSkipped {len(skipped_images)} existing images", fg="yellow", err=True)

    click.secho(f"\nTotal: {len(created_images)} images created", fg="green", err=True)
    click.secho(f"Cohort ID: {cohort.pk}", fg="blue", err=True)


def publish_image_with_specific_isic_id(*, accession, isic_id: str, publisher: User):
    with lock_table_for_writes(IsicId), transaction.atomic():
        if accession.attribution == "":
            accession.attribution = accession.cohort.default_attribution
            accession.save(update_fields=["attribution"])

        isic_id_obj, _ = IsicId.objects.get_or_create(id=isic_id)
        image = Image(isic=isic_id_obj, creator=publisher, accession=accession, public=False)
        image.full_clean()
        image.save()

        embed_iptc_metadata_for_image(image)
        unembargo_image(image=image)


def get_or_create_sample_user():
    username = "sample-data-creator"
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.create_user(
            username=username,
            email="sample-data@example.com",
            is_staff=True,
            is_superuser=True,
        )
    return user


def get_or_create_sample_contributor(user):
    institution_name = "Sample Data Contributor"
    contributor = Contributor.objects.filter(institution_name=institution_name).first()
    if not contributor:
        contributor = Contributor.objects.create(
            institution_name=institution_name,
            institution_url="https://example.com",
            legal_contact_info="sample-data@example.com",
            creator=user,
            default_copyright_license=CopyrightLicense.CC_0,
            default_attribution="Sample Data",
        )
        contributor.owners.add(user)
    return contributor


def create_cohort(user, contributor, name):
    return Cohort.objects.create(
        contributor=contributor,
        creator=user,
        name=name,
        description="Specific ISIC images loaded from S3 for development purposes",
        default_copyright_license=CopyrightLicense.CC_0,
        default_attribution="Sample Data",
    )
