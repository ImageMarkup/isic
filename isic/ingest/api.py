import os

from django.db import transaction
from django.db.models.aggregates import Count
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Field, ModelSchema, Query, Router, Schema
from ninja.pagination import paginate
from ninja.security import django_auth
from pydantic import validator
from s3_file_field.widgets import S3PlaceholderFile

from isic.core.pagination import CursorPagination
from isic.core.permissions import SessionAuthStaffUser, get_visible_objects
from isic.ingest.models import Accession, Cohort, Contributor, MetadataFile
from isic.ingest.services.accession import accession_create
from isic.ingest.services.accession.review import accession_review_bulk_create
from isic.ingest.tasks import update_metadata_task

accession_router = Router()


class AccessionIn(Schema):
    cohort: int
    original_blob: str = Field(..., description="S3 file field value.")

    @validator("original_blob")
    @classmethod
    def validate_s3_file(cls, value: str) -> S3PlaceholderFile:
        s3_file = S3PlaceholderFile.from_field(value)
        if s3_file is None:
            raise ValueError("Invalid S3 file field value.")
        return s3_file


class AccessionOut(ModelSchema):
    class Config:
        model = Accession
        model_fields = ["id"]


@accession_router.post(
    "/", response={201: AccessionOut, 403: dict, 400: dict}, summary="Create an Accession."
)
def create_accession(request: HttpRequest, payload: AccessionIn):
    cohort = get_object_or_404(Cohort, pk=payload.cohort)
    if not request.user.is_staff and not request.user.has_perm("ingest.add_accession", cohort):
        return 403, {"error": "You do not have permission to add accessions to this cohort."}

    return 201, accession_create(
        cohort=cohort,
        creator=request.user,
        original_blob=payload.original_blob,
        original_blob_name=os.path.basename(payload.original_blob.name),
        original_blob_size=payload.original_blob.size,
    )


class AccessionReview(Schema):
    id: int
    value: bool


@accession_router.post(
    "/create-review-bulk/", response={403: dict, 201: dict}, include_in_schema=False
)
def create_review_bulk(request: HttpRequest, payload: list[AccessionReview]):
    if not request.user.is_staff:
        return 403, {"error": "Only staff users may bulk create reviews."}

    accession_review_bulk_create(
        reviewer=request.user,
        accession_ids_values={x.id: x.value for x in payload},
    )
    return 201, {}


cohort_router = Router()
default_cohort_qs = Cohort.objects.annotate(accession_count=Count("accessions"))


class CohortOut(ModelSchema):
    class Config:
        model = Cohort
        model_fields = [
            "id",
            "created",
            "creator",
            "contributor",
            "name",
            "description",
            "default_copyright_license",
            "attribution",
        ]

    accession_count: int = Field(alias="accession_count")


@cohort_router.get("/", response=list[CohortOut], summary="Return a list of cohorts.")
@paginate(CursorPagination)
def cohort_list(request: HttpRequest):
    return get_visible_objects(request.user, "ingest.view_cohort", default_cohort_qs)


@cohort_router.get("/{id}/", response=CohortOut, summary="Retrieve a single cohort by ID.")
def cohort_detail(request: HttpRequest, id: int):
    qs = get_visible_objects(request.user, "ingest.view_cohort", default_cohort_qs)
    return get_object_or_404(qs, id=id)


contributor_router = Router()


class ContributorIn(ModelSchema):
    class Config:
        model = Contributor
        model_fields = [
            "institution_name",
            "institution_url",
            "legal_contact_info",
            "default_copyright_license",
            "default_attribution",
        ]


class ContributorOut(ModelSchema):
    class Config:
        model = Contributor
        model_fields = [
            "id",
            "created",
            "creator",
            "owners",
            "institution_name",
            "institution_url",
            "legal_contact_info",
            "default_copyright_license",
            "default_attribution",
        ]


@contributor_router.get(
    "/", response=list[ContributorOut], summary="Return a list of contributors."
)
@paginate(CursorPagination)
def contributor_list(request: HttpRequest):
    return get_visible_objects(
        request.user, "ingest.view_contributor", Contributor.objects.prefetch_related("owners")
    )


@contributor_router.get(
    "/{id}/", response=ContributorOut, summary="Retrieve a single contributor by ID."
)
def contributor_detail(request: HttpRequest, id: int):
    qs = get_visible_objects(request.user, "ingest.view_contributor", Contributor.objects.all())
    return get_object_or_404(qs, id=id)


@contributor_router.post(
    "/", response={201: ContributorOut}, include_in_schema=False, auth=django_auth
)
@transaction.atomic
def create_contributor(request: HttpRequest, payload: ContributorIn):
    contributor = Contributor.objects.create(creator=request.user, **payload.dict())
    contributor.owners.add(request.user)
    return 201, contributor


metadata_file_router = Router()


class MetadataFileOut(ModelSchema):
    class Config:
        model = MetadataFile
        model_fields = ["id"]


@metadata_file_router.delete(
    "/{id}/", response={204: None}, include_in_schema=False, auth=SessionAuthStaffUser()
)
def delete_metadata_file(request: HttpRequest, id: int):
    metadata_file = get_object_or_404(MetadataFile, id=id)
    # Delete the blob from S3
    metadata_file.blob.delete()
    metadata_file.delete()
    return 204, None


@metadata_file_router.post(
    "/{id}/update_metadata",
    response={202: None},
    include_in_schema=False,
    auth=SessionAuthStaffUser(),
)
def update_metadata(request: HttpRequest, id: int):
    metadata_file = get_object_or_404(MetadataFile, id=id)
    update_metadata_task.delay(request.user.pk, metadata_file.pk)
    return 202, None


autocomplete_router = Router()


@autocomplete_router.get("/cohort/", response=list[CohortOut], include_in_schema=False)
def cohort_autocomplete(request: HttpRequest, query=Query(..., min_length=3)):
    return get_visible_objects(
        request.user,
        "ingest.view_cohort",
        Cohort.objects.filter(name__icontains=query).annotate(accession_count=Count("accessions")),
    )
