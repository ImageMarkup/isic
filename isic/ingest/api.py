from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.db.models.aggregates import Count
from django.shortcuts import get_object_or_404
from django.urls import path
from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from s3_file_field.widgets import S3PlaceholderFile

from isic.auth import IsAuthenticated, IsStaff
from isic.core.api.image import ImageSerializer
from isic.core.models import CopyrightLicense
from isic.core.pagination import paginate
from isic.core.permissions import get_visible_objects
from isic.core.serializers import StrictSerializer
from isic.ingest.models import Accession, Cohort, Contributor, Lesion, MetadataFile
from isic.ingest.models.lesion import get_lesion_count_for_user
from isic.ingest.services.accession import create_accession
from isic.ingest.services.accession.review import bulk_create_accession_reviews
from isic.ingest.tasks import update_metadata_task


class LesionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesion
        fields = [
            "id",
            "images",
            "images_count",
            "longitudinally_monitored",
            "index_image_id",
            "outcome_diagnosis",
            "outcome_diagnosis_1",
        ]

    images = serializers.SerializerMethodField()
    images_count = serializers.IntegerField()
    longitudinally_monitored = serializers.BooleanField()
    index_image_id = serializers.CharField()
    outcome_diagnosis = serializers.CharField()
    outcome_diagnosis_1 = serializers.CharField()

    def get_images(self, obj: Lesion) -> list:
        return ImageSerializer(
            [accession.image for accession in obj.accessions.all() if accession.published],
            many=True,
        ).data


@api_view(["GET"])
@permission_classes([AllowAny])
def lesion_detail(request, id: str):
    qs = get_visible_objects(
        request.user,
        "ingest.view_lesion",
        Lesion.objects.with_total_info().prefetch_related(
            "accessions__image", "accessions__cohort"
        ),
    )
    return Response(LesionSerializer(get_object_or_404(qs, id=id)).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def lesion_list(request):
    # ordering is necessary for the paginator
    qs = get_visible_objects(
        request.user,
        "ingest.view_lesion",
        Lesion.objects.with_total_info()
        .prefetch_related("accessions__image", "accessions__cohort")
        .order_by("id"),
    )
    # the count can be done much more efficiently than the full query
    qs.custom_count = get_lesion_count_for_user(request.user)
    return paginate(request, qs, LesionSerializer)


class AccessionCreateSerializer(StrictSerializer):
    cohort = serializers.IntegerField()
    original_blob = serializers.CharField(help_text="S3 file field value.", trim_whitespace=False)
    metadata = serializers.DictField(default=dict)
    engagement_external_id = serializers.CharField(
        allow_null=True, allow_blank=True, default=None, trim_whitespace=False
    )

    def validate_original_blob(self, value: str) -> S3PlaceholderFile:
        s3_file = S3PlaceholderFile.from_field(value)
        if s3_file is None:
            raise serializers.ValidationError("Invalid S3 file field value.")
        return s3_file


class AccessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = ["id"]


def _metadata_errors(exc: PydanticValidationError) -> dict:
    return {
        "message": "Invalid metadata.",
        "errors": [
            {"field": str(error["loc"][0]) if error["loc"] else "", "message": error["msg"]}
            for error in exc.errors()
        ],
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accession_create(request):
    payload = AccessionCreateSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    original_blob = payload.validated_data["original_blob"]

    cohort = get_object_or_404(Cohort, pk=payload.validated_data["cohort"])
    if not request.user.is_staff and not request.user.has_perm("ingest.add_accession", cohort):
        return Response(
            {"error": "You do not have permission to add accessions to this cohort."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        with transaction.atomic():
            accession = create_accession(
                cohort=cohort,
                creator=request.user,
                original_blob=original_blob,
                original_blob_name=Path(original_blob.name).name,
                original_blob_size=original_blob.size,
                engagement_external_id=payload.validated_data["engagement_external_id"],
            )

            if payload.validated_data["metadata"]:
                accession.update_metadata(request.user, payload.validated_data["metadata"])
    except PydanticValidationError as e:
        return Response(_metadata_errors(e), status=status.HTTP_400_BAD_REQUEST)
    except IntegrityError:
        # cohort wide invariants like "a lesion belongs to one patient" are only enforced by the
        # database here, since a single accession can't be checked against rows it doesn't know
        # about the way a metadata CSV can.
        return Response(
            {"message": "Metadata conflicts with existing cohort data."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(AccessionSerializer(accession).data, status=status.HTTP_201_CREATED)


class AccessionReviewSerializer(StrictSerializer):
    id = serializers.IntegerField()
    value = serializers.BooleanField()


@api_view(["POST"])
@permission_classes([IsStaff])
def accession_review_bulk_create(request):
    payload = AccessionReviewSerializer(data=request.data, many=True)
    payload.is_valid(raise_exception=True)
    bulk_create_accession_reviews(
        reviewer=request.user,
        accession_ids_values={x["id"]: x["value"] for x in payload.validated_data},
    )
    return Response({}, status=status.HTTP_201_CREATED)


default_cohort_qs = Cohort.objects.annotate(accession_count=Count("accessions"))


class CohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cohort
        fields = [
            "id",
            "created",
            "creator",
            "contributor",
            "name",
            "description",
            "default_copyright_license",
            "default_attribution",
            "accession_count",
        ]

    accession_count = serializers.IntegerField()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cohort_list(request):
    return paginate(
        request,
        get_visible_objects(request.user, "ingest.view_cohort", default_cohort_qs),
        CohortSerializer,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cohort_detail(request, id: int):
    qs = get_visible_objects(request.user, "ingest.view_cohort", default_cohort_qs)
    return Response(CohortSerializer(get_object_or_404(qs, id=id)).data)


class ContributorCreateSerializer(serializers.Serializer):
    institution_name = serializers.CharField(
        max_length=255, allow_blank=True, trim_whitespace=False
    )
    institution_url = serializers.URLField(
        max_length=200, allow_blank=True, default="", trim_whitespace=False
    )
    legal_contact_info = serializers.CharField(allow_blank=True, trim_whitespace=False)
    default_copyright_license = serializers.ChoiceField(
        choices=CopyrightLicense.choices, allow_blank=True, default=""
    )
    default_attribution = serializers.CharField(
        max_length=255, allow_blank=True, default="", trim_whitespace=False
    )


class ContributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        fields = [
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


class ContributorAutocompleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        fields = ["id", "institution_name"]


class ContributorCohortSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    accession_count = serializers.IntegerField()


class ContributorDetailSerializer(ContributorSerializer):
    class Meta(ContributorSerializer.Meta):
        fields = [*ContributorSerializer.Meta.fields, "cohorts", "cohort_count", "accession_count"]

    cohorts = ContributorCohortSerializer(many=True)
    cohort_count = serializers.SerializerMethodField()
    accession_count = serializers.SerializerMethodField()

    def get_cohort_count(self, obj: Contributor) -> int:
        return obj.cohorts.count()

    def get_accession_count(self, obj: Contributor) -> int:
        return sum(cohort.accession_count for cohort in obj.cohorts.all())  # type: ignore[attr-defined]


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def contributor_list(request):
    if request.method == "POST":
        return _contributor_create(request)

    return paginate(
        request,
        get_visible_objects(
            request.user,
            "ingest.view_contributor",
            Contributor.objects.prefetch_related("owners"),
        ),
        ContributorSerializer,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def contributor_detail(request, id: int):
    qs = get_visible_objects(
        request.user,
        "ingest.view_contributor",
        Contributor.objects.prefetch_related(
            "owners",
            Prefetch("cohorts", queryset=default_cohort_qs.order_by("-accession_count", "name")),
        ),
    )
    return Response(ContributorDetailSerializer(get_object_or_404(qs, id=id)).data)


@transaction.atomic
def _contributor_create(request):
    payload = ContributorCreateSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    contributor = Contributor.objects.create(creator=request.user, **payload.validated_data)
    contributor.owners.add(request.user)
    return Response(ContributorSerializer(contributor).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsStaff])
def metadata_file_delete(request, id: int):
    metadata_file = get_object_or_404(MetadataFile, id=id)
    metadata_file.delete()
    # Delete the blob from S3, making sure to not reattempt saving the same metadata_file model
    metadata_file.blob.delete(save=False)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsStaff])
def metadata_file_update_metadata(request, id: int):
    metadata_file = get_object_or_404(MetadataFile, id=id)
    update_metadata_task.delay_on_commit(request.user.pk, metadata_file.pk)
    return Response(status=status.HTTP_202_ACCEPTED)


lesion_urlpatterns = [
    path("<id>/", lesion_detail, name="lesion_detail"),
    path("", lesion_list, name="lesion_list"),
]

accession_urlpatterns = [
    path("", accession_create, name="accession_create"),
    path(
        "create-review-bulk/",
        accession_review_bulk_create,
        name="accession_review_bulk_create",
    ),
]

cohort_urlpatterns = [
    path("", cohort_list, name="cohort_list"),
    path("<int:id>/", cohort_detail, name="cohort_detail"),
]

contributor_urlpatterns = [
    path("", contributor_list, name="contributor_list"),
    path("<int:id>/", contributor_detail, name="contributor_detail"),
    path("", contributor_list, name="contributor_create"),
]

metadata_file_urlpatterns = [
    path("<int:id>/", metadata_file_delete, name="metadata_file_delete"),
    path(
        "<int:id>/update_metadata/",
        metadata_file_update_metadata,
        name="metadata_file_update_metadata",
    ),
]
