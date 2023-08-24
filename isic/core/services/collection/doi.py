import logging
import random
from urllib import parse

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
import requests
from requests.exceptions import HTTPError

from isic.core.models.collection import Collection
from isic.core.models.doi import Doi
from isic.core.services.collection import (
    collection_get_creators_in_attribution_order,
    collection_lock,
    collection_update,
)

logger = logging.getLogger(__name__)


def collection_build_doi_preview(*, collection: Collection) -> dict:
    preview = collection_build_doi(
        collection=collection, doi_id=f"{settings.ISIC_DATACITE_DOI_PREFIX}/123456"
    )["data"]["attributes"]
    preview["creators"] = ", ".join([c["name"] for c in preview["creators"]])
    return preview


def collection_build_doi(*, collection: Collection, doi_id: str) -> dict:
    return {
        "data": {
            "type": "dois",
            "attributes": {
                "identifiers": [{"identifierType": "DOI", "identifier": doi_id}],
                "event": "publish",
                "doi": doi_id,
                "creators": [
                    {"name": creator}
                    for creator in collection_get_creators_in_attribution_order(
                        collection=collection
                    )
                ],
                "contributor": f"{collection.creator.first_name} {collection.creator.last_name}",
                "titles": [{"title": collection.name}],
                "publisher": "ISIC Archive",
                "publicationYear": collection.images.order_by("created").latest().created.year,
                # resourceType?
                "types": {"resourceTypeGeneral": "Dataset"},
                # TODO: api.?
                "url": f"https://api.isic-archive.com/collections/{collection.pk}/",
                "schemaVersion": "http://datacite.org/schema/kernel-4",
                "description": collection.description,
                "descriptionType": "Other",
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
    return f"{settings.ISIC_DATACITE_DOI_PREFIX}/{random.randint(10_000, 999_999):06}"


def collection_check_create_doi_allowed(*, user: User, collection: Collection) -> None:
    if not user.has_perm("core.create_doi", collection):
        raise ValidationError("You don't have permissions to do that.")
    elif collection.doi:
        raise ValidationError("This collection already has a DOI.")
    elif not collection.public:
        raise ValidationError("A collection must be public to issue a DOI.")
    elif collection.images.private().exists():
        raise ValidationError("This collection contains private images.")
    elif not collection.images.exists():
        raise ValidationError("An empty collection cannot be the basis of a DOI.")
    elif collection.is_magic:
        raise ValidationError("Magic collections cannot be the basis of a DOI.")


def _datacite_create_doi(doi: dict) -> None:
    r = requests.post(
        f"{settings.ISIC_DATACITE_API_URL}/dois",
        auth=(settings.ISIC_DATACITE_USERNAME, settings.ISIC_DATACITE_PASSWORD),
        timeout=5,
        json=doi,
    )

    try:
        r.raise_for_status()
    except HTTPError:
        logger.exception(f"DOI draft creation failed: {r.json()}")
        raise ValidationError("Something went wrong creating the DOI.")


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
    except HTTPError:
        logger.exception(f"DOI update failed: {r.json()}")
        raise ValidationError("Something went wrong publishing the DOI.")


def collection_create_doi(*, user: User, collection: Collection) -> Doi:
    collection_check_create_doi_allowed(user=user, collection=collection)
    doi_id = collection_generate_random_doi_id()
    draft_doi_dict = collection_build_draft_doi(doi_id=doi_id)
    doi_dict = collection_build_doi(collection=collection, doi_id=doi_id)

    with transaction.atomic():
        # First, create the local DOI record to validate uniqueness within our known set
        doi = Doi(id=doi_id, creator=user, url=f"https://doi.org/{doi_id}")
        doi.full_clean()
        doi.save()

        # Lock the collection, set the DOI on it
        collection_lock(collection=collection)
        collection_update(collection=collection, doi=doi, ignore_lock=True)

        # Reserve the DOI using the draft mechanism.
        # If it fails, transaction will rollback, nothing in our database will change.
        _datacite_create_doi(draft_doi_dict)

    # Convert to a published DOI. If this fails, someone will have to come along later and
    # retry to publish it. (May want a django-admin action for this if it ever happens.)
    _datacite_update_doi(doi_dict, doi_id)

    logger.info("User %d created DOI %s for collection %d", user.id, doi.id, collection.id)

    return doi
