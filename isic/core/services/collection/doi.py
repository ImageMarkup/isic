import csv
import logging
from pathlib import Path
import random
import tempfile
from typing import Any
from urllib import parse
import zipfile

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import connection, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify
import requests
from requests.exceptions import HTTPError

from isic.core.models.collection import Collection
from isic.core.models.doi import Doi
from isic.core.services import image_metadata_csv
from isic.core.services.collection import (
    collection_get_creators_in_attribution_order,
    collection_lock,
    collection_update,
)
from isic.core.tasks import (
    create_doi_bundle_task,
    fetch_doi_citations_task,
    fetch_doi_schema_org_dataset_task,
)
from isic.core.views.doi import LICENSE_TITLES, LICENSE_URIS
from isic.zip_download.api import get_attributions

logger = logging.getLogger(__name__)


def collection_build_doi_preview(*, collection: Collection) -> dict[str, Any]:
    preview = collection_build_doi(
        collection=collection, doi_id=f"{settings.ISIC_DATACITE_DOI_PREFIX}/123456"
    )["data"]["attributes"]
    preview["creators"] = ", ".join([c["name"] for c in preview["creators"]])
    return preview


def collection_build_doi(*, collection: Collection, doi_id: str) -> dict:
    rights = []
    for license_ in (
        collection.images.values_list("accession__copyright_license", flat=True)
        .order_by()
        .distinct()
    ):
        rights.append(  # noqa: PERF401
            {
                "rights": LICENSE_TITLES[license_],
                "rightsUri": LICENSE_URIS[license_],
                "rightsIdentifier": license_,
            }
        )
    return {
        "data": {
            "type": "dois",
            "attributes": {
                "descriptions": [
                    {
                        "description": collection.description,
                        "descriptionType": "Abstract",
                    }
                ],
                "identifiers": [{"identifierType": "DOI", "identifier": doi_id}],
                "event": "publish",
                "doi": doi_id,
                "creators": [
                    {"name": creator}
                    for creator in collection_get_creators_in_attribution_order(
                        collection=collection
                    )
                ],
                "rightsList": rights,
                "titles": [{"title": collection.name}],
                "publisher": "ISIC Archive",
                "publicationYear": collection.images.order_by("created").latest().created.year,
                # resourceType?
                "types": {"resourceTypeGeneral": "Dataset"},
                "url": "https://api.isic-archive.com"
                + reverse("core/doi-detail", kwargs={"slug": slugify(collection.name)}),
                "schemaVersion": "http://datacite.org/schema/kernel-4",
            },
        }
    }


def collection_build_draft_doi(*, doi_id: str) -> dict:
    return {
        "data": {
            "type": "dois",
            "attributes": {
                "doi": doi_id,
            },
        }
    }


def collection_generate_random_doi_id():
    # pad DOI with leading zeros so all DOIs are prefix/6 digits
    return f"{settings.ISIC_DATACITE_DOI_PREFIX}/{random.randint(10_000, 999_999):06}"  # noqa: S311


def collection_check_create_doi_allowed(
    *, user: User, collection: Collection, supplemental_files=None
) -> None:
    if not user.has_perm("core.create_doi", collection):
        raise ValidationError("You don't have permissions to do that.")
    if collection.doi:
        raise ValidationError("This collection already has a DOI.")
    if not collection.public:
        raise ValidationError("A collection must be public to issue a DOI.")
    if collection.images.private().exists():  # type: ignore[attr-defined]
        raise ValidationError("This collection contains private images.")
    if not collection.images.exists():
        raise ValidationError("An empty collection cannot be the basis of a DOI.")
    if collection.is_magic:
        raise ValidationError("Magic collections cannot be the basis of a DOI.")
    if supplemental_files and len(supplemental_files) > 10:
        raise ValidationError("A DOI can only have up to 10 supplemental files.")


def _datacite_create_doi(doi: dict) -> None:
    r = requests.post(
        f"{settings.ISIC_DATACITE_API_URL}/dois",
        auth=(settings.ISIC_DATACITE_USERNAME, settings.ISIC_DATACITE_PASSWORD),
        timeout=5,
        json=doi,
    )

    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.exception("DOI draft creation failed: %s", r.json())
        raise ValidationError("Something went wrong creating the DOI.") from e


def _datacite_update_doi(doi: dict, doi_id: str):
    doi_quoted = parse.quote(doi_id, safe="")  # escape the / for path
    r = requests.put(
        f"{settings.ISIC_DATACITE_API_URL}/dois/{doi_quoted}",
        auth=(settings.ISIC_DATACITE_USERNAME, settings.ISIC_DATACITE_PASSWORD),
        timeout=5,
        json=doi,
    )

    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.exception("DOI update failed: %s", r.json())
        raise ValidationError("Something went wrong publishing the DOI.") from e


def collection_create_doi(*, user: User, collection: Collection, supplemental_files=None) -> Doi:
    collection_check_create_doi_allowed(
        user=user, collection=collection, supplemental_files=supplemental_files
    )

    doi_id = collection_generate_random_doi_id()
    draft_doi_dict = collection_build_draft_doi(doi_id=doi_id)
    doi_dict = collection_build_doi(collection=collection, doi_id=doi_id)

    with transaction.atomic():
        # First, create the local DOI record to validate uniqueness within our known set
        doi = Doi(
            id=doi_id, slug=slugify(collection.name), creator=user, url=f"https://doi.org/{doi_id}"
        )
        doi.full_clean()
        doi.save()

        # Lock the collection, set the DOI on it
        collection_lock(collection=collection)
        collection_update(collection=collection, doi=doi, ignore_lock=True)

        if supplemental_files:
            for supplemental_file in supplemental_files:
                doi.supplemental_files.create(
                    blob=supplemental_file["blob"].name,
                    description=supplemental_file["description"],
                    filename=Path(supplemental_file["blob"].name).name,
                    size=supplemental_file["blob"].size,
                )

        # Reserve the DOI using the draft mechanism.
        # If it fails, transaction will rollback, nothing in our database will change.
        _datacite_create_doi(draft_doi_dict)

    # Convert to a published DOI. If this fails, someone will have to come along later and
    # retry to publish it. (May want a django-admin action for this if it ever happens.)
    _datacite_update_doi(doi_dict, doi_id)

    create_doi_bundle_task.delay_on_commit(doi_id)
    fetch_doi_citations_task.delay_on_commit(doi_id)
    fetch_doi_schema_org_dataset_task.delay_on_commit(doi_id)

    logger.info("User %d created DOI %s for collection %d", user.id, doi.id, collection.id)

    return doi


def collection_create_doi_files(*, doi: Doi) -> None:
    """
    Create the files associated with the DOI.

    This includes the frozen bundle of the collection as well as the metadata csv and license files.
    """
    collection = Collection.objects.select_related("doi").get(doi=doi)
    collection_slug = slugify(collection.name)

    with transaction.atomic():
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

        images = collection.images.select_related("accession").all()

        bundle_filename = f"{collection_slug}.zip"
        with zipfile.ZipFile(bundle_filename, "w") as bundle:
            for image in images.iterator():
                with image.accession.blob.open("rb") as blob:
                    bundle.writestr(f"images/{image.isic_id}.{image.extension}", blob.read())

            # the metadata csv could be large enough that it needs to be written to disk first
            with tempfile.NamedTemporaryFile("w", delete=False) as metadata_file:
                collection_metadata = image_metadata_csv(qs=images)
                writer = csv.DictWriter(metadata_file, fieldnames=next(collection_metadata))
                writer.writeheader()
                for row in collection_metadata:
                    assert isinstance(row, dict)  # noqa: S101
                    writer.writerow(row)
                metadata_file.flush()

                bundle.write(metadata_file.name, "metadata.csv")

            for license_ in (
                images.values_list("accession__copyright_license", flat=True).order_by().distinct()
            ):
                bundle.writestr(
                    f"licenses/{license_}.txt",
                    render_to_string(f"zip_download/{license_}.txt"),
                )

            attributions = get_attributions(images.values_list("accession__attribution", flat=True))
            bundle.writestr("attribution.txt", "\n\n".join(attributions))

    # this should be done outside of the above transaction since it uses
    # repeatable read and will potentially take a long time to complete. otherwise
    # if the other DOI related tasks modified the DOI we would get a "could not
    # serialize" error. see
    # https://www.postgresql.org/docs/current/transaction-iso.html#XACT-REPEATABLE-READ
    with (
        Path(bundle_filename).open("rb") as bundle_file,
        Path(metadata_file.name).open("rb") as metadata_file,
        transaction.atomic(),  # necessary for select_for_update
    ):
        doi = Doi.objects.select_for_update().get(id=doi.id)
        doi.bundle = File(bundle_file)
        doi.bundle_size = Path(bundle_filename).stat().st_size
        doi.metadata = File(metadata_file, name=f"{collection_slug}.csv")
        doi.metadata_size = Path(metadata_file.name).stat().st_size
        doi.save()

        Path(bundle_filename).unlink()
