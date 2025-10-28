from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from urllib import parse

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.db.models import QuerySet
from django.urls import reverse
from django.utils.text import slugify
from requests.exceptions import HTTPError
from requests_toolbelt.sessions import BaseUrlSession

from isic.core.models.doi import (
    AbstractDoi,
    Doi,
    DoiRelatedIdentifier,
    DraftDoi,
)
from isic.core.services.collection import (
    collection_get_creators_in_attribution_order,
    collection_lock,
    collection_update,
)
from isic.core.services.snapshot import snapshot_images
from isic.core.tasks import (
    create_doi_bundle_task,
    fetch_doi_citations_task,
    fetch_doi_schema_org_dataset_task,
)
from isic.core.views.doi import LICENSE_TITLES, LICENSE_URIS
from isic.ingest.services.publish import unembargo_image

if TYPE_CHECKING:
    from collections.abc import Iterable
    from urllib.parse import ParseResult

    from isic.core.api.doi import RelatedIdentifierIn
    from isic.core.models.collection import Collection

logger = logging.getLogger(__name__)


def collection_build_doi(
    *,
    collection: Collection,
    doi_id: str,
    is_draft: bool,
    related_identifiers: QuerySet[DoiRelatedIdentifier] | None = None,
) -> dict:
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

    datacite_related_identifiers = []
    if related_identifiers:
        datacite_related_identifiers = [
            {
                "relatedIdentifier": related_id.related_identifier,
                "relatedIdentifierType": related_id.related_identifier_type,
                "relationType": related_id.relation_type,
            }
            for related_id in related_identifiers
        ]

    attributes = {
        "descriptions": [
            {
                "description": collection.description,
                "descriptionType": "Abstract",
            }
        ],
        "identifiers": [{"identifierType": "DOI", "identifier": doi_id}],
        "doi": doi_id,
        "creators": [
            {"name": creator}
            for creator in collection_get_creators_in_attribution_order(collection=collection)
        ],
        "rightsList": rights,
        "titles": [{"title": collection.name}],
        "publisher": "ISIC Archive",
        "publicationYear": collection.images.order_by("created").latest().created.year,
        "types": {"resourceTypeGeneral": "Dataset"},
        "url": "https://api.isic-archive.com"
        + reverse("core/doi-detail", kwargs={"slug": slugify(collection.name)}),
        "schemaVersion": "http://datacite.org/schema/kernel-4",
    }

    if not is_draft:
        attributes["event"] = "publish"

    if datacite_related_identifiers:
        attributes["relatedIdentifiers"] = datacite_related_identifiers

    return {
        "data": {
            "type": "dois",
            "attributes": attributes,
        }
    }


def collection_check_create_draft_doi_allowed(
    *,
    user: User,
    collection: Collection,
    supplemental_files: Iterable[dict[str, str]] | None = None,
    related_identifiers: Iterable[RelatedIdentifierIn] | None = None,
) -> None:
    if not user.has_perm("core.create_doi", collection):
        raise ValidationError("You don't have permissions to do that.")
    if hasattr(collection, "doi") or hasattr(collection, "draftdoi"):
        raise ValidationError("This collection already has a DOI.")
    if not collection.images.exists():
        raise ValidationError("An empty collection cannot be the basis of a DOI.")
    if collection.is_magic:
        raise ValidationError("Magic collections cannot be the basis of a DOI.")
    if supplemental_files and len(supplemental_files) > 10:
        raise ValidationError("A DOI can only have up to 10 supplemental files.")
    if (
        related_identifiers
        and len([r for r in related_identifiers if r.relation_type == "IsDescribedBy"]) > 1
    ):
        raise ValidationError("A DOI can only have one IsDescribedBy related identifier.")


def _datacite_session() -> BaseUrlSession:
    api_url: ParseResult | None = settings.ISIC_DATACITE_API_URL
    if api_url is None:
        raise ValueError("ISIC_DATACITE_API_URL is not set.")

    session = BaseUrlSession(
        base_url=f"{api_url.scheme}://{api_url.hostname}"
        + (f":{api_url.port}" if api_url.port else "")
    )
    session.auth = (api_url.username, api_url.password)
    return session


def _datacite_create_draft_doi(doi: dict) -> None:
    with _datacite_session() as session:
        resp = session.post(
            "/dois",
            json=doi,
            timeout=5,
        )

    try:
        resp.raise_for_status()
    except HTTPError as e:
        logger.exception("DOI draft creation failed: %s", resp.json())
        raise ValidationError("Something went wrong creating the DOI.") from e


def _datacite_promote_draft_doi_to_findable(doi: dict, doi_id: str):
    # escape the / for path
    doi_quoted = parse.quote(doi_id, safe="")
    with _datacite_session() as session:
        resp = session.put(
            f"/dois/{doi_quoted}",
            json=doi,
            timeout=5,
        )

    try:
        resp.raise_for_status()
    except HTTPError as e:
        logger.exception("DOI update failed: %s", resp.json())
        raise ValidationError("Something went wrong publishing the DOI.") from e


def collection_create_draft_doi(
    *,
    user: User,
    collection: Collection,
    description: str,
    supplemental_files: Iterable[dict[str, str]] | None = None,
    related_identifiers: Iterable[RelatedIdentifierIn] | None = None,
) -> DraftDoi:
    collection_check_create_draft_doi_allowed(
        user=user,
        collection=collection,
        supplemental_files=supplemental_files,
        related_identifiers=related_identifiers,
    )

    with transaction.atomic():
        draft_doi = DraftDoi(slug=slugify(collection.name), collection=collection, creator=user)
        draft_doi.full_clean()
        draft_doi.save()

        collection_update(collection=collection, description=description, ignore_lock=True)
        collection_lock(collection=collection)

        if supplemental_files:
            for supplemental_file in supplemental_files:
                draft_doi.supplemental_files.create(
                    blob=supplemental_file["blob"].name,
                    description=supplemental_file["description"],
                    filename=Path(supplemental_file["blob"].name).name,
                    size=supplemental_file["blob"].size,
                )

        if related_identifiers:
            for related_identifier in related_identifiers:
                draft_doi.related_identifiers.create(
                    relation_type=related_identifier.relation_type,
                    related_identifier_type=related_identifier.related_identifier_type,
                    related_identifier=related_identifier.related_identifier,
                )

        draft_doi_dict = collection_build_doi(
            collection=collection,
            doi_id=draft_doi.id,
            is_draft=True,
            related_identifiers=draft_doi.related_identifiers.all(),
        )

        _datacite_create_draft_doi(draft_doi_dict)

    create_doi_bundle_task.delay_on_commit(draft_doi.id, "DraftDoi")
    fetch_doi_citations_task.delay_on_commit(draft_doi.id, "DraftDoi")
    fetch_doi_schema_org_dataset_task.delay_on_commit(draft_doi.id, "DraftDoi")

    return draft_doi


def collection_create_doi_files(*, doi: AbstractDoi) -> None:
    """
    Create the files associated with the DOI.

    This includes the frozen bundle of the collection as well as the metadata csv and license files.
    """
    collection = doi.collection
    collection_slug = slugify(collection.name)

    snapshot_filename, metadata_filename = snapshot_images(
        qs=collection.images.select_related("accession"),
        supplemental_files=doi.supplemental_files.all(),
    )

    try:
        # this should not be done in the same transaction as the snapshotting since it uses
        # repeatable read and will potentially take a long time to complete. otherwise
        # if the other DOI related tasks modified the DOI we would get a "could not
        # serialize" error. see
        # https://www.postgresql.org/docs/current/transaction-iso.html#XACT-REPEATABLE-READ
        with (
            Path(snapshot_filename).open("rb") as bundle_file,
            Path(metadata_filename).open("rb") as metadata_file,
            transaction.atomic(),  # necessary for select_for_update
        ):
            doi = doi.__class__.objects.select_for_update().get(id=doi.id)
            doi.bundle = File(bundle_file, name=f"{collection_slug}.zip")
            doi.bundle_size = Path(snapshot_filename).stat().st_size
            doi.metadata = File(metadata_file, name=f"{collection_slug}.csv")
            doi.metadata_size = Path(metadata_file.name).stat().st_size
            doi.save()
    finally:
        Path(snapshot_filename).unlink()
        Path(metadata_filename).unlink()


def draft_doi_publish(*, user: User, draft_doi: DraftDoi) -> Doi:
    """Publish a draft DOI to become a final, findable DOI."""
    collection = draft_doi.collection

    if not user.has_perm("core.create_doi", collection):
        raise ValidationError("You don't have permissions to publish this DOI.")

    for image in collection.images.private().select_related("accession").iterator():
        unembargo_image(image=image)

    collection_update(collection=collection, public=True, ignore_lock=True)

    with transaction.atomic():
        doi = Doi.objects.create(
            id=draft_doi.id,
            slug=draft_doi.slug,
            collection=draft_doi.collection,
            creator=draft_doi.creator,
            bundle=draft_doi.bundle,
            bundle_size=draft_doi.bundle_size,
            metadata=draft_doi.metadata,
            metadata_size=draft_doi.metadata_size,
            citations=draft_doi.citations,
            schema_org_dataset=draft_doi.schema_org_dataset,
        )

        for draft_supplemental_file in draft_doi.supplemental_files.all():
            doi.supplemental_files.create(
                blob=draft_supplemental_file.blob,
                description=draft_supplemental_file.description,
                filename=draft_supplemental_file.filename,
                size=draft_supplemental_file.size,
                order=draft_supplemental_file.order,
            )

        for draft_related_identifier in draft_doi.related_identifiers.all():
            doi.related_identifiers.create(
                relation_type=draft_related_identifier.relation_type,
                related_identifier_type=draft_related_identifier.related_identifier_type,
                related_identifier=draft_related_identifier.related_identifier,
            )

        doi_dict = collection_build_doi(
            collection=collection,
            doi_id=doi.id,
            is_draft=False,
            related_identifiers=doi.related_identifiers.all(),
        )

        _datacite_promote_draft_doi_to_findable(doi_dict, doi.id)

        # delete all draft records (this will cascade to supplemental files and related identifiers)
        draft_doi.delete()

    # trigger async tasks for final DOI
    create_doi_bundle_task.delay_on_commit(doi.id, "Doi")
    fetch_doi_citations_task.delay_on_commit(doi.id, "Doi")
    fetch_doi_schema_org_dataset_task.delay_on_commit(doi.id, "Doi")

    return doi
