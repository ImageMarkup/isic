from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from pydantic import field_validator
from s3_file_field.widgets import S3PlaceholderFile

from isic.core.models.collection import Collection
from isic.core.models.doi import DoiRelatedIdentifier
from isic.core.services.collection.doi import collection_create_doi

router = Router()


class RelatedIdentifierIn(Schema):
    relation_type: str
    related_identifier_type: str
    related_identifier: str


class CreateDOIIn(Schema):
    collection_id: int
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
        DoiRelatedIdentifier.validate_related_identifiers(
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
    response={200: None, 403: dict, 409: dict},
    summary="Create a DOI for a collection.",
    include_in_schema=False,
)
def create_doi(request, payload: CreateDOIIn):
    collection = get_object_or_404(
        Collection.objects.select_related("doi"), pk=payload.collection_id
    )

    if not request.user.has_perm("core.create_doi", collection):
        return 403, {"error": "You do not have permission to create a DOI."}

    collection_create_doi(
        user=request.user,
        collection=collection,
        supplemental_files=payload.supplemental_files,
        related_identifiers=payload.related_identifiers,
    )
