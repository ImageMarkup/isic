from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from pydantic import field_validator
from s3_file_field.widgets import S3PlaceholderFile

from isic.core.models.collection import Collection
from isic.core.models.doi import DraftDoi, DraftDoiRelatedIdentifier
from isic.core.services.collection.doi import collection_create_draft_doi
from isic.core.tasks import publish_draft_doi_task

router = Router()


class RelatedIdentifierIn(Schema):
    relation_type: str
    related_identifier_type: str
    related_identifier: str


class CreateDOIIn(Schema):
    collection_id: int
    description: str
    supplemental_files: list[dict[str, str]]
    related_identifiers: list[RelatedIdentifierIn] = []

    @field_validator("supplemental_files")
    def validate_supplemental_files(cls, v):  # noqa: N805
        if len(v) > 10:
            raise ValueError("You can only upload up to 10 supplemental files.")
        return v

    @field_validator("supplemental_files")
    def validate_supplemental_files_descriptions(cls, v):  # noqa: N805
        if any(not file["description"] for file in v):
            raise ValueError("All supplemental files must have a description.")
        return v

    @field_validator("supplemental_files")
    def parse_s3_file_field_values(cls, v):  # noqa: N805
        for file in v:
            file["blob"] = S3PlaceholderFile.from_field(file["blob"])
            if file["blob"] is None:
                raise ValueError("Invalid S3 file field value.")
        return v

    @field_validator("related_identifiers")
    def validate_related_identifiers(cls, v):  # noqa: N805
        DraftDoiRelatedIdentifier.validate_related_identifiers(
            [
                {
                    "relation_type": related_identifier.relation_type,
                    "related_identifier_type": related_identifier.related_identifier_type,
                    "related_identifier": related_identifier.related_identifier,
                }
                for related_identifier in v
            ]
        )
        return v


@router.post(
    "/",
    response={201: dict, 403: dict, 409: dict},
    summary="Create a draft DOI for a collection.",
    include_in_schema=False,
)
def create_doi(request, payload: CreateDOIIn):
    collection = get_object_or_404(Collection, pk=payload.collection_id)

    if not request.user.has_perm("core.create_doi", collection):
        return 403, {"error": "You do not have permission to create a DOI."}

    draft_doi = collection_create_draft_doi(
        user=request.user,
        collection=collection,
        description=payload.description,
        supplemental_files=payload.supplemental_files,
        related_identifiers=payload.related_identifiers,
    )

    return 201, {"slug": draft_doi.slug}


class UpdateDraftDOIIn(Schema):
    description: str


@router.patch(
    "/{draft_doi_slug}/",
    response={200: dict, 403: dict, 404: dict},
    summary="Update a draft DOI.",
    include_in_schema=False,
)
def update_draft_doi(request, draft_doi_slug: str, payload: UpdateDraftDOIIn):
    from isic.core.services.collection import collection_update

    draft_doi = get_object_or_404(
        DraftDoi.objects.select_related("collection"), slug=draft_doi_slug
    )

    if not request.user.has_perm("core.create_doi", draft_doi.collection):
        return 403, {"error": "You do not have permission to update this DOI."}

    collection_update(
        collection=draft_doi.collection, description=payload.description, ignore_lock=True
    )

    return 200, {"message": "Draft DOI updated successfully."}


@router.post(
    "/{draft_doi_slug}/publish/",
    response={200: dict, 403: dict, 404: dict, 409: dict},
    summary="Publish a draft DOI to make it findable.",
    include_in_schema=False,
)
def publish_draft_doi(request, draft_doi_slug: str):
    with transaction.atomic():
        draft_doi = get_object_or_404(
            DraftDoi.objects.select_for_update().select_related("collection"), slug=draft_doi_slug
        )

        if not request.user.has_perm("core.create_doi", draft_doi.collection):
            return 403, {"error": "You do not have permission to publish this DOI."}

        if draft_doi.is_publishing:
            return 409, {"error": "This DOI is already being published."}

        draft_doi.is_publishing = True
        draft_doi.save(update_fields=["is_publishing"])

        publish_draft_doi_task.delay_on_commit(draft_doi.id, request.user.id)

    messages.add_message(request, messages.INFO, "Publishing DOI, this may take several minutes.")

    return 200, {"message": "DOI publish task started successfully."}
